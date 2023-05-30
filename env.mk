# env.mk (GNU Make)				-*- makefile-gmake -*-

##
## Caveats:
##
## - define the 'all' target or other default mk target,
##   before including env.mk
##

HOST_PYTHON?=	python3

## RUNNER_OS would typically be set under GitHub Workflow actions
## https://docs.github.com/en/actions/learn-github-actions/variables
RUNNER_OS?=	$(shell uname -o)

## virtual environment dir for tasks
ENV_DIR?=	env
## common file for virtual enviornmentso
ENV_CFG=	${ENV_DIR}/pyvenv.cfg

## basedir for bin cmds under ENV_DIR
## as created by -m virtualenv
ifeq (${RUNNER_OS},Windows)
ENV_BINDIR=		${ENV_DIR}/Scripts
else
ENV_BINDIR=		${ENV_DIR}/bin
endif


## project configuration - default uses pyproject.toml
PROJECT_CFG?=	pyproject.toml
## optional requirments.in (project file)
ADDL_REQ?=	$(wildcard requirements.in)
## optional requirements.local (user file)
LOCAL_REQ?=	$(wildcard requirements.local)
## the requirements.txt file to be generated by pip-compile
REQ_TXT?=	requirements.txt

REQ_DEPENDS=	${PROJECT_CFG} ${ADDL_REQ} ${LOCAL_REQ}


## utility script for virtual environment installation,
## does not install virtualenv in ${ENV_DIR}
PROJECT_PY?=	project.py

## optional features for the project config, used with pip-compile
PYPROJECT_EXTRAS?=	dev

##
## shell scripts for tasks
##

ACTIVATE?=		${ENV_BINDIR}/pipenv run

ifndef ENV_CMD_template
define ENV_CMD_template=
ifndef ENV_CMD_$(1)
PYPI_$(1)?=		$(1)
ENV_CMD_$(1)?=		$${ENV_BINDIR}/$(1)
ENV_$(1)?=		$${ENV_CMD_$(1)}
ENV_REQ_$(1)?=		$${ENV_CFG}

$${ENV_CMD_$(1)}:	$${ENV_REQ_$(1)}
	$${ENV_pip} install $${PIP_OPTIONS} $${PYPI_$(1)}

PYPI_$(1)-install:	$${ENV_CMD_$(1)}
.PHONY:		$(1)-install
endif
endef ## ENV_CMD_template end
endif

## tools to be used under virutal env, in targets defined below
ENV_BIN+=	python3 pip-compile pip-sync pipenv

PYPI_pip-compile=	pip-tools
ENV_REQ_pip-sync=	${ENV_CMD_pip-compile}

## define variables for each tool to be used under virtual env
$(foreach BIN,${ENV_BIN},$(eval $(call ENV_CMD_template,${BIN})))

## pip will be installed under the ${ENV_CFG} make target
ENV_CMD_pip?=		${ENV_BINDIR}/pip
ENV_pip?=		${ENV_CMD_pip}
${ENV_CMD_pip}:		${ENV_CFG}

##
## options for shell scripts
##

## shared wheel/sdist cache for pip and pip-compile
PIP_CACHE?=		${HOME}/.cache/pip
## options for pip, directly and via pip-compile
PIP_OPTIONS?=		--no-build-isolation -v --cache-dir="${PIP_CACHE}"
## options for pip-compile (pip-tools)
ifndef PIP_COMPILE_OPTIONS
PIP_COMPILE_OPTIONS=	--cache-dir="${PIP_CACHE}" --resolver=backtracking -v
PIP_COMPILE_OPTIONS+=	--pip-args "${PIP_OPTIONS}"
PIP_COMPILE_OPTIONS+=	$(foreach OPT,${PYPROJECT_EXTRAS},--extra ${OPT})
endif
## options for pip-sync (pip-tools)
PIP_SYNC_OPTIONS?=	-v --ask --pip-args "${PIP_OPTIONS}"

##
## configuration for stamp.mk
##

ENV_STAMP_TGTS=		pip-install pip-tools-sync pip-tools-upgrade
ENV_STAMP_CLEAN=	$(foreach T,${ENV_STAMP_TGTS},$(call stamp_file,${T}))
## add to the bindings for stamp.mk
STAMP_TGTS+=		${ENV_STAMP_TGTS}

##
## main makefile
##

include stamp.mk

env: ${ENV_CFG}

env-clean:
	rm -f ${ENV_STAMP_CLEAN}

env-realclean: env-clean
	rm -rf ${ENV_DIR}

## sync - shorthand mk target, this will call pip-sync (pip-tools)
sync: ${pip-tools-sync_stamp}
sync-clean: pip-tools-sync-clean

## upgrade - similarly, a shorthand mk target
upgrade: ${pip-tools-upgrade_stamp}
upgrade-clean: pip-tools-upgrade-clean

## pip install
${pip-install_stamp}: ${REQ_TXT} ${ENV_CMD_pip}
	${ENV_pip} install ${PIP_OPTIONS} -r ${REQ_TXT}
	$(call mkstamp_sh,$@)

## pip-sync (pip-tools)
${pip-tools-sync_stamp}: ${REQ_TXT} ${ENV_CMD_pip_SYNC}
	${ENV_pip-sync} ${PIP_SYNC_OPTIONS}
	$(call mkstamp_sh,$@)

## this should not reinstall the environment if pyvenv.cfg already exists
${ENV_CFG}: ${PROJECT_PY}
	if ! [ -e ${ENV_CFG} ]; then VIRTUALENV_OPTS="--no-periodic-update" \
		${HOST_PYTHON} ${PROJECT_PY} ensure_env ${ENV_DIR}; \
		${ENV_pip} install pipenv; \
	fi

## generate a requirements.txt as a composite of project/user requirements
${REQ_TXT}: ${ENV_CMD_pip-compile} ${REQ_DEPENDS}
	${ENV_pip-compile} ${PIP_COMPILE_OPTIONS} \
		-o ${REQ_TXT} ${PROJECT_CFG} ${ADDL_REQ} ${LOCAL_REQ}

## pip-compile with ---upgrade && pip install
${pip-tools-upgrade_stamp}: ${REQ_TXT} ${ENV_CMD_pip}
	${ENV_pip-compile} ${PIP_COMPILE_OPTIONS} --upgrade \
		-o ${REQ_TXT} ${PROJECT_CFG} ${ADDL_REQ} ${LOCAL_REQ}
	${MAKE} ${pip-install_stamp}
	$(call mkstamp_sh,$@)

.PHONY:	env env-clean env-realclean sync sync-clean upgrade upgrade-clean

