## Makefile (GNU Make)

SETENV?=	env
HOST_PYTHON?=	python3
PY_VERSION?=	$(shell V=$$(${PYTHON} --version); V=$${V#Python }; echo $${V%.*})

ENV_DIR?=  	${CURDIR}/env
ENV_CFG=	${ENV_DIR}/pyvenv.cfg

INSTALL_ENV?=	${CURDIR}/install_env.py

PIP_REQ?=	requirements.txt
LOCAL_REQ?=	requirements.local

## shell scripts and shell commands
SOURCE?=		.
ACTIVATE?=		${SOURCE} ${ENV_DIR}/bin/activate;

ENV_CMD_PYTHON?=	${ENV_DIR}/bin/python3
ENV_PYTHON?=		${ACTIVATE} ${ENV_CMD_PYTHON}

ENV_CMD_PIP?=		${ENV_DIR}/bin/pip
ENV_PIP?=		${ACTIVATE} ${ENV_CMD_PIP}

ENV_CMD_PIP_COMPILE?=	${ENV_DIR}/bin/pip-compile
ENV_PIP_COMPILE?=	${ACTIVATE} ${ENV_CMD_PIP_COMPILE}

ENV_CMD_PIP_SYNC?=	${ENV_DIR}/bin/pip-sync
ENV_PIP_SYNC?=		${ACTIVATE} ${ENV_CMD_PIP_SYNC}

## options for shell scripts
PIP_OPTIONS?=		--no-build-isolation -v
## options for invoking pip-compile
PIP_COMPILE_OPTIONS?=	--resolver=backtracking -v --extra dev --pip-args "${PIP_OPTIONS}"
## options for invoking pip-sync
PIP_SYNC_OPTIONS?=	-v --ask --pip-args "${PIP_OPTIONS}"

all: pip-install

env: ${ENV_CFG}

req-update: ${PIP_REQ}

sync: ${PIP_REQ} piptools-sync

pip-install: ${PIP_REQ} ${ENV_CMD_PIP}
	${ENV_PIP} install ${PIP_OPTIONS} -r ${PIP_REQ}

pip-upgrade: ${PIP_REQ} ${ENV_CMD_PIP}
	${ENV_PIP} install ${PIP_OPTIONS} --upgrade -r ${PIP_REQ}

piptools-sync: ${PIP_REQ} ${ENV_CMD_PIP_SYNC}
	${ENV_PIP_SYNC} ${PIP_SYNC_OPTIONS}

${ENV_CFG}: ${INSTALL_ENV}
	if ! [ -e ${ENV_CFG} ]; then \
		${HOST_PYTHON} ${INSTALL_ENV} ${ENV_DIR}; \
	fi

${ENV_CMD_PIP}: ${ENV_CFG}

${ENV_CMD_PIP_COMPILE}: ${ENV_CFG}
	${ENV_PIP} install ${PIP_OPTIONS} pip-tools

${ENV_CMD_PIP_SYNC}: ${ENV_CMD_PIP_COMPILE}

${PIP_REQ}: ${ENV_CMD_PIP_COMPILE} pyproject.toml
	if [ -e ${LOCAL_REQ} ]; then EXTRA_REQ='${EXTRA_REQ} ${LOCAL_REQ}'; fi; \
		${ENV_PIP_COMPILE} ${PIP_COMPILE_OPTIONS} -o ${PIP_REQ} pyproject.toml $${EXTRA_REQ}

.PHONY:	all env req-update pip-install pip-upgrade sync piptools-sync
