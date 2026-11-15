//! Versioned linear-way profile rules; independent of SQL argument/vector adapters.
use crate::{coordinates::OutputCrs, pbf::Way, source::Source};
use duckdb_neo::{AsDuckDB, Error, Result};
use std::collections::BTreeSet;
pub(crate) const PROFILE_VERSION: &str = "1.0.0";
pub(crate) const SCHEMA_VERSION: &str = "1.0.0";

#[derive(AsDuckDB)]
pub(crate) struct SourceRef {
    pub osm_type: String,
    pub osm_id: i64,
    pub osm_version: Option<i32>,
}

#[derive(AsDuckDB)]
pub(crate) struct Issue {
    pub severity: String,
    pub code: String,
    pub field: Option<String>,
    pub raw_value: Option<String>,
    pub message: String,
}
impl Issue {
    fn warning(code: &str, key: &str, raw: &str) -> Self {
        Self {
            severity: "warning".into(),
            code: code.into(),
            field: Some(key.into()),
            raw_value: Some(raw.into()),
            message: "value cannot be represented by this scalar field".into(),
        }
    }
    pub fn geometry(code: &str) -> Self {
        Self {
            severity: "error".into(),
            code: code.into(),
            field: Some("geometry".into()),
            raw_value: None,
            message: "required road geometry cannot be established".into(),
        }
    }
}

pub(crate) struct Feature {
    pub way: Way,
    pub refs: Vec<SourceRef>,
    pub points: Vec<(f64, f64)>,
    pub issues: Vec<Issue>,
    pub speed: Option<f64>,
    pub oneway: Option<String>,
    pub rejected: bool,
}

pub(crate) fn selected(w: &Way) -> bool {
    w.tags.contains_key("highway") && w.tags.get("area").is_none_or(|s| s != "yes")
}

fn speed(raw: &str) -> Option<f64> {
    let raw = raw.trim_matches(|c: char| c.is_ascii_whitespace());
    let (number, factor) = [(" km/h", 1.), (" mph", 1.609344), (" knots", 1.852)]
        .into_iter()
        .find_map(|(suffix, factor)| raw.strip_suffix(suffix).map(|n| (n, factor)))
        .unwrap_or((raw, 1.));
    let mut parts = number.split('.');
    let digits = |s: &str| !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit());
    if !digits(parts.next()?) || parts.next().is_some_and(|p| !digits(p)) || parts.next().is_some()
    {
        return None;
    }
    let value: f64 = number.parse::<f64>().ok()? * factor;
    (value.is_finite() && value > 0.).then_some(value)
}

fn attribute<T>(
    w: &Way,
    key: &str,
    issues: &mut Vec<Issue>,
    parse: impl FnOnce(&str) -> Option<T>,
) -> Option<T> {
    let prefix = format!("{key}:");
    let mut scoped = false;
    for (k, v) in &w.tags {
        if k.starts_with(&prefix) {
            scoped = true;
            issues.push(Issue::warning(
                if k == &format!("{key}:conditional") {
                    "conditional_value"
                } else {
                    "unsupported_value"
                },
                k,
                v,
            ));
        }
    }
    if scoped {
        return None;
    }
    let raw = w.tags.get(key)?;
    if raw.contains('@') {
        issues.push(Issue::warning("conditional_value", key, raw));
        return None;
    }
    let result = parse(raw);
    if result.is_none() {
        issues.push(Issue::warning("unsupported_value", key, raw));
    }
    result
}

pub(crate) fn project(source: &Source, way: Way, crs: OutputCrs, report: bool) -> Result<Feature> {
    let mut issues = Vec::new();
    let speed = attribute(&way, "maxspeed", &mut issues, speed);
    let oneway = attribute(&way, "oneway", &mut issues, |raw| match raw {
        "yes" | "1" | "true" => Some("forward".to_owned()),
        "-1" => Some("backward".to_owned()),
        "no" | "0" | "false" => Some("both".to_owned()),
        _ => None,
    });
    let mut refs = vec![SourceRef {
        osm_type: "way".into(),
        osm_id: way.id,
        osm_version: way.version,
    }];
    let mut seen = BTreeSet::new();
    let mut points = Vec::with_capacity(way.refs.len());
    let (mut missing, mut invalid, mut poles) = (false, false, false);
    for id in &way.refs {
        match source.node(*id)? {
            Some((version, x, y)) => {
                if seen.insert(*id) {
                    refs.push(SourceRef {
                        osm_type: "node".into(),
                        osm_id: *id,
                        osm_version: version,
                    });
                }
                invalid |= !crate::coordinates::valid_wgs84(x, y);
                poles |= y.abs() >= 90.;
                points.push((x, y));
            }
            None => missing = true,
        }
    }
    invalid |= points.len() < 2
        || points
            .first()
            .is_none_or(|first| points.iter().all(|p| p == first));
    let code = if missing {
        Some("missing_reference")
    } else if invalid {
        Some("invalid_geometry")
    } else if poles && crs == OutputCrs::WebMercator {
        Some("transformation_failed")
    } else {
        None
    };
    if let Some(code) = code {
        issues.push(Issue::geometry(code));
    }
    let mut feature = Feature {
        way,
        refs,
        points,
        issues,
        speed,
        oneway,
        rejected: code.is_some(),
    };
    feature.enforce(report)?;
    Ok(feature)
}

impl Feature {
    pub fn reject_transform(&mut self, report: bool) -> Result<()> {
        self.issues.push(Issue::geometry("transformation_failed"));
        self.rejected = true;
        self.enforce(report)
    }
    fn enforce(&mut self, report: bool) -> Result<()> {
        if self.rejected && !report {
            let code = self
                .issues
                .last()
                .map(|i| i.code.as_str())
                .unwrap_or("invalid_geometry");
            return Err(Error::invalid_input(format!("{code}: way {}", self.way.id)));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn numeric_speed_grammar_and_units() {
        for (raw, n) in [
            ("50", 50.),
            (" 12.5 km/h ", 12.5),
            ("30 mph", 48.28032),
            ("10 knots", 18.52),
        ] {
            assert!((speed(raw).unwrap() - n).abs() < 1e-10);
        }
        for raw in [
            "0",
            "-5",
            "+5",
            "NaN",
            "1e2",
            "1.",
            ".5",
            "50;80",
            "none",
            "DE:urban",
            "50 kph",
            "30 @ (wet)",
            "1.2.3",
        ] {
            assert_eq!(speed(raw), None, "{raw}");
        }
    }
}
