slidesho.bas: Slideshow display for RC2014+Tektronix 4010-series terminals
==========================================================================

![A Tektronix 4006-1 vector graphics storage terminal, with an RC2014 Zed Pro
Pride kit computer perched atop it, displaying a 3-view drawing of a biplane.](
slidesho.jpg "A Tektronix 4006-1 terminal and an RC2014 Zed Pro Pride kit
computer showing a 3-view drawing of a biplane.")

This directory contains utilities for displaying a slideshow of vector graphics
files on a Tektronix 4010-series terminal (including the 4006-1) attached to
certain configurations of the [RC2014](https://rc2014.co.uk/) kit computer. For
more information and acknowledgements, please browse [`slidesho.bas`](
slidesho.bas), the program that runs under [BBC BASIC (Z80)](
https://www.bbcbasic.co.uk/bbcbasic/z80basic.html) on the RC2014, and
[`make_slidesho_distro.py`](make_slidesho_distro.py), a utility for preparing
data file distributions for `slidesho.bas` on a modern computer.


Demo
----
The included Makefile exercises `make_slidesho_distro.py` as well as other
programs in this repository to demonstrate the process of preparing slideshow
data for `slidesho.bas`.


-- _[Tom Stepleton](mailto:stepleton@gmail.com), 8 July 2024, London_
