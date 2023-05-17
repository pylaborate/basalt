## stamp.mk (GNU Make)				-*- makefile-gmake -*-

## caveats
##
## - define or append to STAMP_TGTS before including this GNU Make
##   Makefile, e.g STAMP_TGTS+= build docs test
##
## - include stamp.mk before defining any stamp-file targets.
##
##   For each <name> in STAMP_TGTS, stamp.mk will define a make
##   target <name> and a make target <name>-clean.
##
##   This will also append <name>_stamp to the varible, ALL_MK_STAMP
##
## - For each <name> in STAMP_TGTS, a ${<name>_stamp} target
##   should be defined within the including Makfile, after
##   including stamp.mk
##
##   The ${<name>_stamp} target should provide the actual
##   implementation for the <name> target
##
##   An example is available in ./env.mk
##
## - the following GNU Make expression should be included at
##   the end of each ${<name>_stamp} target:
##
##	$(call mkstamp_sh,$@)
##
##   This will ensure that the resulting shell command will be
##   included in the target shell expression. This will create
##   the stamp file at the end of the succesful completion of
##   the shell expression.
##
## - to remove the stamp file for any ${<name>_stamp} target,
##   run 'gmake <name>-clean'
##
## - for purpose of convenience in calling gmake, a phony target
##   <name> is defined for each ${<name>_stamp} target, i.e
##   for each name in ${STAMP_TGTS}
##
##   This target will run the corresonding <name>-clean target,
##   before running the ${<name>_stamp} target
##
## - If the <name>-clean target should be implemented external
##   to stamp.mk:
##
##     1) define a variable <name>_cleanflag=<name>-clean
##        before including stamp.mk in the calling Makefile
##
##     2) include the following at the end of the <name>-clean
##        target:
##
##		rm -f $(call stamp_file,$(subst -clean,,$@))
##
##    Example:
##
##	STAMP_TGTS+=		pong6
##	PONG6_CLEANFILES?=	src/pong/*6.a src/pong/*6.so src/pong/pong6
##
##	pong6_cleanflag=	pong6-clean
##	include stamp.mk
##
##	all: pong6
##
##	pong6-clean:
##		rm -f ${PONG6_CLEANFILES}
##		rm -f $(call stamp_file,$(subst -clean,,$@))
##
##	${pong6_stamp}: $(wildcard src/pong/*.c src/pong/*.h)
##		make -C src/pong PING=ping6
##		$(call mkstamp_sh,$@)
##
##	clean:	$(foreach T,${STAMP_TGTS},${T}-clean)
##		rm -f ${ALL_MK_STAMP}
##
## remarks for maintenance
##
## - gmake 'ifndef' is a test on variables, and not a test on mk tgts
##
## remarks from design
##
## - inpired after mk-file conventions for bmake (BSD Make)
##
## - designed for application with GNU Make, for portability with
##   common development tools in popular Linux distributions

STAMP_DIR?=	${CURDIR}/.mkdone
STAMP_TGTS?=

mkstamp_sh?=	mkdir -p $(dir $(1)) && touch $(1)
stamp_file?=	${STAMP_DIR}/.${1}_done

## template for stamp-file tgts, stamp-clean tgts
##
## The 'defined' tests (variables) should serve to
## ensure that these tgts will not be redefined if
## stamp.mk is included from more than one Makefile
## in the build.
##
## This also serves to allow for overriding the definition
## from template, if the mk guard-variable is defined before
## including stamp.mk
##
## This is a template for $(eval $(call ...))
## referenced on GNU Make info docs
##
ifndef STAMP_template
define STAMP_template =

ifndef $(1)_stamp
$(1)_stamp?=		$$(call stamp_file,$(1))
$(1): $${$(1)_cleanflag} $${$(1)_stamp}
.PHONY: $(1)
ALL_MK_STAMP+=		$${$(1)_stamp}
endif

ifndef $(1)_cleanflag
$(1)_cleanflag?=	$(1)-clean
$${$(1)_cleanflag}:
	rm -f $$(call stamp_file,$$(subst -clean,,$$@))
.PHONY: $${$(1)_cleanflag}
endif

endef ## end of STAMP_template
endif

## ensure all stamp variables, stamp tgts are defined
$(foreach T,${STAMP_TGTS},$(eval $(call STAMP_template,${T})))

## end of stamp.mk
