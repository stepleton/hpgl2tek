# An example usage of ../text.py, ../hpgl2tek.py, and make_slidesho_distro.py
# to make a ZIP archive file (demo_slideshow.zip) containing a three-slide
# slideshow for use with slidesho.bas on a suitably-appointed RC2014/Tektronix
# 4010-compatible terminal setup. It's NOT necessary to execute this Makefile
# to use any of the code distributed alongside it.
#
# Revision history
# ----------------
#
# This section records the development of this file as part of the `hpgl2tek`
# project at <http://github.com/stepleton/hpgl2tek>.
#
# 8 July 2024: Initial release.
# (Tom Stepleton, stepleton@gmail.com, London)

TEXT = ../text.py
H2T = ../hpgl2tek.py
MSD = ./make_slidesho_distro.py

HPGLS := slide1.hpgl slide2.hpgl slide3.hpgl
TEKS := $(HPGLS:.hpgl=.tek)

all: demo_slideshow.zip

slide1.hpgl: Makefile
	$(TEXT) -f timesi -o $@ Slide 1

slide2.hpgl: Makefile
	$(TEXT) -f gothicita -o $@ Slide 2

slide3.hpgl: Makefile
	$(TEXT) -f scriptc -o $@ Slide 3

%.tek: %.hpgl
	$(H2T) $^ -d tek4010 -o $@

CATALOG: $(TEKS)
	printf "slide1.tek\tOne\nslide2.tek\tTwo\nslide3.tek\tThree\n" > $@

demo_slideshow.zip: CATALOG
	$(MSD) -o $@ $^

clean:
	rm -f $(HPGLS) $(TEKS) CATALOG demo_slideshow.zip

.PHONY: all clean
