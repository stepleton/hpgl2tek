hpgl2tek: For making graphics and animations on Tektronix storage tube systems
==============================================================================

![A simulated Tektronix 4010 terminal showing the graphic the Makefile makes: a
kind of Hershey fonts "sampler" that says "McTeague et al. US Pat. 3,956,662
Cathode ray storage tube having a target dielectric provided with particulate
segments of collector electrode extending therethrough".](
crsthatdpwpsoceet.png "A simulated Tektronix 4010 terminal showing the graphic
the Makefile makes.")

This repository contains a collection of Python programs useful for displaying
vector graphics on Tektronix 4010-series terminals and on 4050-series computers
with the R12 "fast graphics" ROM expansion. One program facilitates the
creation of old-fashioned frame-by-frame animations composed of many individual
vector graphics frames (which you must film with a camera pointed at the
screen). For further documentation and information about software dependencies,
please see comments within the programs, which are these:

### [hpgl2tek.py](hpgl2tek.py)

Converts [HPGL](https://en.wikipedia.org/wiki/HP-GL) files for display on some
old Tektronix computers and terminals.  This program can compose multiple HPGL
files into a single output file after scaling and transforming their contents
in various ways. All of this same functionality is available to other programs
when this file is used as a module.
   
### [text.py](text.py)

Creates HPGL files that contain text rendered in [Hershey fonts](
https://en.wikipedia.org/wiki/Hershey_fonts). The Hershey fonts are free
rudimentary vector fonts made by the U.S. Navy in 1967 for use with vector CRT
displays. They're still useful in that application, and they're also useful for
plotters.

### [animate.py](animate.py)

Creates animations for rendering on suitably-equipped Tektronix computers.
Reads in a file that uses a hastily-cobbled language to describe a multi-frame
vector graphics animation via compositions of lines and moving HPGL file
elements. Output may go to an MP4 file for viewing on a modern computer or to a
ZIP file containing files that can be used by a Tektronix 4050-series computer
with the R12 "fast graphics" ROM pack. (The files must be placed on a tape
cartridge or the [McGraw 4050 Flash Drive tape drive emulator](
https://github.com/mmcgraw74/Tektronix-4050-GPIB-Flash-Drive).)

### [zipchopper.py](zipchopper.py)

Chop up an animation ZIP archive to something Flash-drive compatible. The 4050
Flash Drive is an extremely useful device, but it seems like it may have issues
handling file numbers greater than 250 or so. (Or this could be the Tek
instead.) Some ZIP files have animations with more frames than that, so this
file breaks those down into separate zip files that have been renumbered,
counting up from 1. No ZIP file will have more than 226 files inside of it.

### [slidesho](slidesho/README.md)

Utilities for displaying a slideshow of vector graphics files on a Tektronix
4010-series terminal (including the 4006-1) attached to certain configurations
of the [RC2014](https://rc2014.co.uk/) kit computer.


Demo
----
The included Makefile exercises `hpgl2tek.py` and `text.py` to generate a
vector graphic suitable for rendering on a Tektronix 4010-compatible terminal.
On a modern Unix-alike, you can experience it by opening up an xterm in
Tektronix mode (`xterm -t -fg green`) and typing `make show`.


Nobody owns hpgl2tek
--------------------

This collection of utility programs, software libraries, and documentation
distributed alongside them are released into the public domain without any
warranty. See the [LICENSE](LICENSE) file for details.


Acknowledgements
----------------

It would not have been possible for me to write this software without the help
of the following people and resources:

- [bitsavers.org](http://bitsavers.org)'s archived technical documentation.
- Monty McGraw's [archived Tektronix 4050-series programs and technical
  documentation](https://github.com/mmcgraw74/Tektronix-4051-4052-4054-Program-Files).
- The "Flash Drive" Tektronix 4924 tape drive emulator [[1]](
  https://github.com/Twilight-Logic/AR488_Store), [[2]](
  https://github.com/mmcgraw74/Tektronix-4050-GPIB-Flash-Drive), [[3]](
  https://forum.vcfed.org/index.php?threads/tektronix-4050-gpib-flash-drive-now-available.1238891/page-6#post-1281423)
  by Monty McGraw and John (?).
- J.L. for allowing me to borrow a Tektronix 4054A with Option 30!


-- _[Tom Stepleton](mailto:stepleton@gmail.com), 22 May 2024, London_
