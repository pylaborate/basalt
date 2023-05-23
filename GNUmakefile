## Makefile (GNU Make)

SHELL=		bash

ENV_DIR?=	env

APIDOC_DIR?=	${SITE_DIR}/api
SRC_DIR?=	src

BUILD_DIR?=	build
SITE_DIR?=	${BUILD_DIR}/site
STAMP_DIR=	${BUILD_DIR}/.mkdone

TOP_PACKAGES?=	pylaborate.basalt pylaborate.common_staging

PDOC3_CFGOPT?=	show_source_code=False
PDOC3_OPT?=	--html --output-dir ${APIDOC_DIR} $(foreach C,${PDOC3_CFGOPT},--config "${C}")
PDOC_BIN?=	${ENV_BINDIR}/pdoc3

PYTEST_BIN?=	${ENV_BINDIR}/pytest

FLAKE8_BIN?=	${ENV_BINDIR}/flake8

CLEAN_DIRS?=	${SITE_DIR} ${STAMP_DIR}

RUN?=		@set -x;

STAMP_TGTS+=	docs lint test

py_sources=	$(wildcard ${1}/*.py ${1}/*/*.py ${1}/*/*/*.py)

PY_SOURCEDIRS=	$(foreach P,${TOP_PACKAGES},${SRC_DIR}/$(subst .,/,${P}))
## PY_SOURCES: usable as a stale-state flag in make tgts
PY_SOURCES=	$(foreach P,${PY_SOURCEDIRS},$(call py_sources,${P}))


## define the all tgt before including env.mk
all: pip-install

## include stamp.mk before defining stamp tgts
include stamp.mk
include env.mk

${PDOC_BIN}: ${ENV_CFG}
	${ENV_pip} install ${PIP_OPTIONS} $(notdir $@)

${PYTEST_BIN}: ${ENV_CFG}
	${ENV_pip} install ${PIP_OPTIONS} $(notdir $@)

${FLAKE8_BIN}: ${ENV_CFG}
	${ENV_pip} install ${PIP_OPTIONS} $(notdir $@)

## to re-build docs, run 'gmake cleandocs docs'
${docs_stamp}: ${PDOC_BIN} ${PY_SOURCES}
	${RUN} for PKG in ${TOP_PACKAGES}; do echo "# -- building docs for $${PKG}"; \
		${ACTIVATE} ${PDOC_BIN} ${PDOC3_OPT} $${PKG}; done
	$(call mkstamp_sh,$@)

## to re-run tests, run 'gmake test-clean test'
${test_stamp}: ${PYTEST_BIN} ${PY_SOURCES}
	${ACTIVATE} ${PYTEST_BIN}
	$(call mkstamp_sh,$@)

${lint_stamp}: ${FLAKE8_BIN} ${PY_SOURCES}
# 	fail on syntax errors, undefined names
	${FLAKE8_BIN} --count --select=E9,F63,F7,F82 --show-source --statistics ${PY_SOURCEDIRS}
	$(call mkstamp_sh,$@)

## docs-clean is a tgt defined in stamp.mk
cleandocs: docs-clean
	rm -f ${docs_stamp}
	if [ ! -e ${SITE_DIR} ]; then exit; fi; \
		find ${SITE_DIR} -maxdepth 1 -mindepth 1 -exec rm -rf {} +

clean: cleandocs
	rm -f ${all_mk_stamps}
	for D in ${CLEAN_DIRS}; do if [ -e $${D} ]; then rmdir $${D}; fi; done

.PHONY: all test cleandocs ${STAMP_TGTS}

