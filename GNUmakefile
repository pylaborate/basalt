## Makefile (GNU Make)

SHELL=		bash

PROJECT_DIR?=	${CURDIR}
ENV_DIR?=	${PROJECT_DIR}/env

APIDOC_DIR?=	${SITE_DIR}/api
SRC_DIR?=	${PROJECT_DIR}/src

BUILD_DIR?=	${CURDIR}/build
SITE_DIR?=	${BUILD_DIR}/site
STAMP_DIR=	${BUILD_DIR}/.mkdone

TOP_PACKAGES?=	pylaborate.basalt pylaborate.libpy_staging

PDOC3_CFGOPT?=	show_source_code=False
PDOC3_OPT?=	--html --output-dir ${APIDOC_DIR} $(foreach C,${PDOC3_CFGOPT},--config "${C}")
PDOC_BIN?=	${ENV_DIR}/bin/pdoc3

PYTEST_BIN?=	${ENV_DIR}/bin/pytest

CLEAN_DIRS?=	${SITE_DIR} ${STAMP_DIR}

RUN?=		@set -x;

STAMP_TGTS+=	docs test

pkg_sources=	$(wildcard ${SRC_DIR}/$(subst .,/,${1})/*.py \
			${SRC_DIR}/$(subst .,/,${1})/*/*.py \
			${SRC_DIR}/$(subst .,/,${1})/*/*/*.py)

PY_SOURCES=	$(foreach P,${TOP_PACKAGES},$(call pkg_sources,${P}))

## define the all tgt before including env.mk
all: pip-install

## include stamp.mk before defining stamp tgts
include stamp.mk
include env.mk

${PDOC_BIN}:
	${ENV_pip} install ${PIP_OPTIONS} $(notdir $@)

${PYTEST_BIN}:
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

## docs-clean is a tgt defined in stamp.mk
cleandocs: docs-clean
	rm -f ${docs_stamp}
	if [ ! -e ${SITE_DIR} ]; then exit; fi; \
		find ${SITE_DIR} -maxdepth 1 -mindepth 1 -exec rm -rf {} +

clean: cleandocs
	rm -f ${all_mk_stamps}
	for D in ${CLEAN_DIRS}; do if [ -e $${D} ]; then rmdir $${D}; fi; done

.PHONY: all test cleandocs ${STAMP_TGTS}

