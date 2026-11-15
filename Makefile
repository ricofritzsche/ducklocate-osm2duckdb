.PHONY: configure debug release test_debug test_release

PROJ_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

EXTENSION_NAME=ducklocate

# Mark the extension as C_STRUCT_UNSTABLE: DuckDB 2.x requires the _init_c_api_v2 entrypoint.
# Binaries load only in the exact TARGET_DUCKDB_VERSION, not in newer DuckDB releases.
USE_UNSTABLE_C_API=1
CAPI_VERSION=2

# Target DuckDB version
TARGET_DUCKDB_VERSION=v2.0.0

all: configure debug

# Include makefiles from DuckDB
include extension-ci-tools/makefiles/c_api_extensions/base.Makefile
include extension-ci-tools/makefiles/c_api_extensions/rust.Makefile

# Native-only adaptation of the pinned template; lockfile required for every build.
TARGET_INFO+=--package ducklocate --locked $(if $(PROBES),--features foundation-probes)
NATIVE_TEST_MODE=$(if $(PROBES),probe,normal)

# Keep synthetic symbols out of the deliverable artifacts.
ifneq ($(PROBES),)
EXTENSION_BUILD_PATH=./build/probes
endif
TEST_RUNNER_DEBUG=$(TEST_RUNNER_BASE) --external-extension $(EXTENSION_BUILD_PATH)/debug/$(EXTENSION_FILENAME)
TEST_RUNNER_RELEASE=$(TEST_RUNNER_BASE) --external-extension $(EXTENSION_BUILD_PATH)/release/$(EXTENSION_FILENAME)

# Refresh metadata on every build (the upstream helper otherwise caches an old HEAD).
.PHONY: foundation_identity
foundation_identity:
	python3 scripts/build_identity.py
build_extension_library_debug build_extension_library_release: foundation_identity

# Upstream pins the runner commit; pin its two Python support packages too.
configure/python-ready: configure/venv requirements-dev.txt scripts/configure_python.py
	$(PYTHON_VENV_BIN) scripts/configure_python.py

configure: configure/python-ready platform foundation_identity

debug: build_extension_library_debug build_extension_with_metadata_debug
release: build_extension_library_release build_extension_with_metadata_release

test_debug: test_extension_debug
	$(PYTHON_VENV_BIN) scripts/native_checks.py $(EXTENSION_BUILD_PATH)/debug/$(EXTENSION_FILENAME) --expect-mode $(NATIVE_TEST_MODE)

test_release: test_extension_release
	$(PYTHON_VENV_BIN) scripts/native_checks.py $(EXTENSION_BUILD_PATH)/release/$(EXTENSION_FILENAME) --expect-mode $(NATIVE_TEST_MODE)
