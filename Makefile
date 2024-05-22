# An example usage of text.py and hpgl2tek.py to create a Hershey fonts
# "sampler" saying the name of a patent that was important to Tektronix
# computer display storage tubes. It's NOT necessary to execute this makefile
# to use hpgl2tek.py or any of the files distributed alongside it.
#
# For near-instant gratification on your latter-day Unix computer, open up
# an xterm in Tektronix mode (`xterm -t -fg green`) and type `make show`.
#
# Forfeited into the public domain with NO WARRANTY. Read LICENSE for details.
#
# Revision history
# ----------------
#
# This section records the development of this file as part of the `hpgl2tek`
# project at <http://github.com/stepleton/hpgl2tek>.
#
# 22 May 2024: Initial release.
# (Tom Stepleton, stepleton@gmail.com, London)

TEXT = ./text.py
H2T = ./hpgl2tek.py

# Cathode ray storage tube having a target dielectric provided with particulate
# segments of collector electrode extending therethrough.

HPGLS := patent.hpgl
HPGLS += crst.hpgl ha.hpgl td.hpgl pw.hpgl ps.hpgl o.hpgl ce.hpgl et.hpgl
PNGS := $(HPGLS:.hpgl=.png)

all: pngs crsthatdpwpsoceet.tek

show: crsthatdpwpsoceet.tek
	@clear
	@cat crsthatdpwpsoceet.tek
	@sleep 10

crsthatdpwpsoceet.tek: $(HPGLS) Makefile
	$(H2T) -o $@ $^ \
	-t \
	0:s0.5!y320,\
	1:y225,\
	2:r4!s0.3!y150,\
	3:s0.6!y75,\
	4:r4!s0.5!y0,\
	5:s0.85!y-75,\
	6:r4!s0.1!y-150,\
	7:s0.7!y-225,\
	8:r4!s0.9!y-320

hpgls: $(HPGLS)

pngs: $(PNGS)

%.png: %.hpgl
	$(H2T) $^ -d png -o $@

patent.hpgl: Makefile
	$(TEXT) -f timesi -o $@ McTeague et al. US Pat. 3,956,662

crst.hpgl: Makefile
	$(TEXT) -f gothicita -o $@ Cathode ray storage tube

ha.hpgl: Makefile
	$(TEXT) -f scriptc -o $@ having a

td.hpgl: Makefile
	$(TEXT) -f gothiceng -o $@ Target Dielectric

pw.hpgl: Makefile
	$(TEXT) -f scriptc -o $@ provided with

ps.hpgl: Makefile
	$(TEXT) -f rowmand -o $@ PARTICULATE SEGMENTS

o.hpgl: Makefile
	$(TEXT) -f scriptc -o $@ of

ce.hpgl: Makefile
	$(TEXT) -f gothicger -o $@ collector electrode

et.hpgl: Makefile
	$(TEXT) -f scriptc -o $@ extending therethrough

clean:
	rm -f *.hpgl *.png *.tek

.PHONY: all clean show
