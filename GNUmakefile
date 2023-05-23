## Makefile (GNU Make)

SHELL=		bash

ENV_DIR?=	env

APIDOC_DIR?=	${SITE_DIR}/api
SRC_DIR?=	src
TEST_DIR?=	test

BUILD_DIR?=	build
SITE_DIR?=	${BUILD_DIR}/site
STAMP_DIR=	${BUILD_DIR}/.mkdone

TOP_PACKAGES?=	pylaborate.basalt pylaborate.common_staging

PDOC3_CFGOPT?=	show_source_code=False
PDOC3_OPT?=	--html --output-dir ${APIDOC_DIR} $(foreach C,${PDOC3_CFGOPT},--config "${C}")

CLEAN_DIRS?=	${SITE_DIR} ${STAMP_DIR}

RUN?=		@set -x;

STAMP_TGTS+=	docs-run lint-ci test-run

py_sources=	$(wildcard ${1}/*.py ${1}/*/*.py ${1}/*/*/*.py)

PY_SOURCEDIRS=	$(foreach P,${TOP_PACKAGES},${SRC_DIR}/$(subst .,/,${P}))
## PY_SOURCES: usable as a stale-state flag in make tgts
PY_SOURCES=	$(foreach P,${PY_SOURCEDIRS},$(call py_sources,${P}))

ENV_BIN?=	pdoc3 pytest flake8

## define the all tgt before including env.mk
all: pip-install

## include stamp.mk before defining stamp tgts
include stamp.mk
include env.mk


## to re-build docs, run 'gmake cleandocs docs'
${docs-run_stamp}: ${ENV_CMD_pdoc3} ${PDOC_BIN} ${PY_SOURCES}
	${RUN} for PKG in ${TOP_PACKAGES}; do echo "# -- building docs for $${PKG}"; \
		${ENV_CMD_pdoc3} ${PDOC3_OPT} $${PKG}; done
	$(call mkstamp_sh,$@)

## to re-run tests, run 'gmake test-clean test'
${test-run_stamp}: ${ENV_CMD_pytest} ${PY_SOURCES}
	${ENV_CMD_pytest} ${TEST_DIR}
	$(call mkstamp_sh,$@)

${lint-ci_stamp}: ${ENV_CMD_flake8} ${PY_SOURCES}
# 	fail on syntax errors, undefined names
	${ENV_CMD_flake8} --count --select=E9,F63,F7,F82 --show-source --statistics ${PY_SOURCEDIRS}
	$(call mkstamp_sh,$@)

## docs-clean is a tgt defined in stamp.mk
cleandocs: docs-run-clean
	rm -f ${docs_stamp}
	if [ ! -e ${SITE_DIR} ]; then exit; fi; \
		find ${SITE_DIR} -maxdepth 1 -mindepth 1 -exec rm -rf {} +

docs: cleandocs docs-run

test: test-run-clean test-run

clean: cleandocs
	rm -f ${all_mk_stamps}
	for D in ${CLEAN_DIRS}; do if [ -e $${D} ]; then rmdir $${D}; fi; done

.PHONY: all cleandocs docs test clean ${STAMP_TGTS}

