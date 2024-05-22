#!/usr/bin/python3
"""Create animations for rendering on suitably-equipped Tektronix computers.

Forfeited into the public domain with NO WARRANTY. Read LICENSE for details.

Reads in a file that uses a hastily-cobbled language to describe a multi-frame
vector graphics animation via compositions of lines and moving HPGL file
elements. Output may go to an MP4 file for viewing on a modern computer or to a
ZIP file containing files that can be used by a Tektronix 4050-series computer
with the R12 "fast graphics" ROM pack. (The files must be placed on a tape
cartridge or the McGraw Flash Drive tape drive emulator.)

Basic usage information can be obtained via the -h flag to this program. For
information on the animation file language, see the section below.

This program is released into the public domain without any warranty. For
details, refer to the LICENSE file distributed with this program, or, if it's
missing, to:
  - https://github.com/stepleton/hpgl2tek/blob/main/LICENSE
For further information, visit http://unlicense.org.

This program originated at https://github.com/stepleton/hpgl2tek, and may have
been modified if obtained elsewhere.

Dependencies
------------

OpenCV and NumPy (video file generation), plus the hpgl2tek module distributed
alongside this file.

Animation file language
-----------------------

Animation files make use of the MS Windows .INI-style idiom used by Python's
[configparser](https://docs.python.org/3/library/configparser.html) library.

Files must contain an `[animation]` section:

   [animation]
   fps = 25
   duration = 6.2

where `fps` is the animation's frame rate in frames per second, and `duration`
is the animation's duration in seconds.

All remaining sections describe a graphical element drawn to the screen as
part of the animation. The names of each section must be unique (and cannot be
`[DEFAULT]`) but otherwise are arbitrary and of no significance to the program.
Parameters in each section include:

- `transform`: (optional) a string of transformation commands for the element
  in the same format as used for the `-t` flag to hpgl2tek.py (except without
  the `N:` prefix indicating which element you wish to transform.

- `file`: the only mandatory parameter, specifying a simple HPGL file
  containing drawing data for this graphical element.

- `start`: (optional, default 0.0) a number in [0.0, 1.0] indicating when in
  the duration of the video the element should first appear.

- `end`: (optional, default 1.0) a number in [0.0, 1.0] indicating when in the
  duration of the video the element should disappear forever.

- `path`: (optional) Control points of a Bezier spline that the element will
  trace at a constant velocity between the `start` and `end` time points. Paths
  are specified as space-separated x,y pairs where x and y are relative to the
  centre of the screen. The order of the spline is the number of x,y pairs less
  one; two pairs yields a linear spline, three a quadratic spline, four a cubic
  spline, and so on. If you only want to deal with cubic splines, then you will
  probably want to define two graphical elements that display in contiguous
  non-overlapping time intervals and use separate, contiguous splines. Note
  that the element's motion here *adds* to any displacement you may have
  specified in `transform`.

- `rose`: (optional) Perturb the location of the element by nudging it around
  a [rose curve](https://en.wikipedia.org/wiki/Rose_(mathematics)). Parameters
  for the rose are space-separated "words" that start with a few letters and
  end with a number, like `r1.1`: the letters say which parameter you're
  specifying and the numbers are the value you're assigning to that parameter.
  The perturbation is calculated as described in the docstring of the Rose
  class, whose attributes are abbreviated here as follows:
  - `k`: abbreviated as `k` 
  - `nu`: `nu`
  - `rotate`: `r`
  - `stretch_x`: `sx`
  - `stretch_y`: `sy`
  - `t_offset`: `dt`
  The element's motion *adds* to any displacement specified in `transform` and
  `path`.

- `blink`: (optional) Blink the element according to the three comma-separated
  numbers. Say the value of this parameter is `1.1,2.2,0.5`: the element will
  repeat being visible for 1.1 seconds then invisible for 2.2 seconds, and the
  "clock" for this behaviour will be set to 0.5 (so, half a second into the
  element being visible) at the first frame of the animation.

- `lines`: (optional) Extra lines to draw in association with this element. The
  format for this parameter matches the `-l` flag to hpgl2tek.py. These lines
  aren't affected by `transform`, `path`, and `rose` but do obey `start`,
  `end`, and `blink`.

Revision history
----------------

This section records the development of this file as part of the `hpgl2tek`
project at <http://github.com/stepleton/hpgl2tek>.

22 May 2024: Initial release.
(Tom Stepleton, stepleton@gmail.com, London)
"""

import argparse
import configparser
import contextlib
import cv2
import dataclasses
import io
import math
import numpy as np
import os
import random
import subprocess
import sys
import tempfile
import zipfile

import hpgl2tek

from typing import BinaryIO, Iterator


XTERM = '/usr/bin/xterm'
CAT = '/bin/cat'


def _define_flags() -> argparse.ArgumentParser:
  """Defines an `ArgumentParser` for command-line flags used by this program."""
  flags = argparse.ArgumentParser(
      description=('Compose basic HPGL files into animation frames for '
                   'various Tektronix storage tube-based graphical terminals '
                   'and computers. (Or into video files for modern computers '
                   'too.)'))

  flags.add_argument('-o', '--output',
                     help=('Destination file for the animation output '
                           'file. Leave blank to write to standard output.'),
                     type=argparse.FileType('w'), default=sys.stdout)

  flags.add_argument('-d', '--device',
                     help=('Create output for particular video display '
                           'devices. tek4050r12zip creates a zip file '
                           'containing R12 "fast graphics" image data files '
                           'and a BASIC program for displaying them (requires '
                           'the -n argument); video creates an mp4 video '
                           'file.'))

  flags.add_argument('-n', '--file_number',
                     help=('Output files created by --device=tek4050r12zip '
                           'are expected to be placed on a McGraw USB Flash '
                           'Drive device. Filenames will use this number and '
                           'numbers that follow: there will be a total of K+1 '
                           'files, where K is the number of animation '
                           'frames.'), type=int)

  flags.add_argument('-a', '--automate',
                     help=('Automate animation picture-taking. If a number '
                           'greater than 0, then when a picture is drawn, the '
                           'tek4050r12zip BASIC program emits a short string '
                           'to the Option 10 printer interface on port @53 '
                           '(triggering the camera shutter) and then uses the '
                           '!PAUSE function on the TransEra 741 RTC module to '
                           'sleep this many seconds (may be fractional) '
                           'before clearing the screen and automatically '
                           'advancing to the next animation frame. (If 0 or '
                           'less, use user-definable key 1 to advance to the '
                           'next frame manually; no string is printed to port '
                           '@53.'), type=float, default=0.0)

  flags.add_argument('animation_file', nargs='?',
                     help=('Animation program file. Leave blank to read from '
                           'standard input.'),
                     type=argparse.FileType('r'), default=sys.stdin)

  flags.add_argument('-m', '--monitor',
                     help=('Display animation frames in an xterm window as '
                           'they are being created. Requires you to have '
                           'installed xterm on your system.'),
                     action='store_true')

  flags.add_argument('-s', '--origin_shift',
                     help=('Displace the animation by some small amount to '
                           'avoid burn-in on actual Tek hardware. This flag '
                           "is useful if you've disabled the origin shift "
                           'circuit in your 4050-series computer so that '
                           'subsequent animation frames are all co-'
                           'registered. May cause this program to fail if a '
                           'piece of of drawing adjacent to the edge of the '
                           'display gets shifted off screen. Affects '
                           'tek4050r12zip outputs only.'),
                     action='store_true')

  return flags


# Types
Point = tuple[float, float]
Points = tuple[Point, ...]


def _spline(points: Points, t: float) -> tuple[float, float]:
  """Calculate parametric location t along a spline."""
  if len(points) == 1:
    return points[0]
  else:
    lerps: Points = tuple(
        ((1 - t)*x1 + t*x2, (1 - t)*y1 + t*y2)  # IYKYK
        for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]))
    return _spline(lerps, t)


def _spline_to_segment_points(
    control_points: tuple[tuple[float, float], ...],
    segments: int = 100,
) -> tuple[tuple[float, float], ...]:
  # First, generate a lookup table that approximates a function mapping t to
  # distance along the curve.
  t_to_dist_lut = [0.0]
  x_old, y_old = control_points[0]
  for t in ((s + 1)/(3*segments) for s in range(3*segments)):
    x, y = _spline(control_points, t)
    t_to_dist_lut.append(
        t_to_dist_lut[-1] + math.sqrt((x - x_old)**2 + (y - y_old)**2))
    x_old, y_old = x, y

  # Normalise the lookup table so that the distance is 1.0.
  t_to_dist_lut = [d / t_to_dist_lut[-1] for d in t_to_dist_lut]

  # Compute segment points for equally-spaced distances along the spline.
  segment_points = [control_points[0]]
  lut_index = 0
  for d in ((s + 1)/segments for s in range(segments)):
    # Find the t value for distance d.
    while t_to_dist_lut[lut_index + 1] < d:
      lut_index += 1
    lo, hi = t_to_dist_lut[lut_index:(lut_index + 2)]
    t = (lut_index + (d - lo)/(hi - lo or math.inf))/(3*segments)
    # Append the spline value for this interpolated t.
    segment_points.append(_spline(control_points, t))

  # Convert the list to a tuple and return.
  return tuple(segment_points)


class Path:
  """A Bezier path, approximated by equal-length linear segments."""
  segment_points: tuple[tuple[float, float], ...]

  def __init__(self,
               control_points: tuple[tuple[float, float], ...],
               segments: int = 100):
    """Initialise a Path.

    Args:
      control_points: Spline control points --- x,y tuples.
      segments: Number of equal-length linear segments to approximate by.
    """
    self.segment_points = _spline_to_segment_points(control_points, segments)

  def at(self, d: float) -> tuple[float, float]:
    """Interpolated position at fraction d along the spline's length.

    Args:
      d: Value in [0, 1].

    Returns:
      x, y coordinate of the point at d's fraction of the spline's length.
    """
    # Find which two segment points d lies between, and where in between.
    segments = len(self.segment_points) - 1
    sp_index = min(int(d*segments), segments - 1)
    lo, hi = sp_index/segments, (sp_index + 1)/segments
    d_frac = (d - lo)/(hi - lo or math.inf)

    # Interpolate between the two segment points.
    (x_lo, y_lo), (x_hi, y_hi) = self.segment_points[sp_index:sp_index+2]
    return (1 - d_frac)*x_lo + d_frac*x_hi, (1 - d_frac)*y_lo + d_frac*y_hi


@dataclasses.dataclass
class Rose:
  """Position perturbation in the form of a linearly-transformed rose curve.

  Calculated thus:

  r := cos(k * (t_abs + t_offset))
  θ := nu * (t_abs + t_offset)
  dx := r * cos(θ) * stretch_x
  dy := r * sin(θ) * stretch_y
  dx := dx * cos(rotate) - dy * sin(rotate)
  dy := dx * sin(rotate) + dy * cos(rotate)
  """
  k: float = 1.0          # Rose curve k parameter
  nu: float = 1.0         # Rotational speed parameter
  stretch_x: float = 1.0  # Scale the curve's X axis prior to rotation
  stretch_y: float = 1.0  # Scale the curve's Y axis prior to rotation
  rotate: float = 0.0     # Rotate the curve this many radians after scaling
  t_offset: float = 0.0   # Offset the t_abs input by this amount

  def at(self, t_abs: float) -> tuple[float, float]:
    """Perturbation at absolute time t_abs.

    Args:
      t_abs: Absolute animation time.

    Returns:
      dx, dy perturbation of the point at absolute time t_abs.
    """
    r = math.cos(self.k * (t_abs + self.t_offset))
    theta = self.nu * (t_abs + self.t_offset)
    dx = r * math.cos(theta) * self.stretch_x
    dy = r * math.sin(theta) * self.stretch_y
    sin = math.sin(self.rotate)
    cos = math.cos(self.rotate)
    dx, dy = (dx * cos - dy * sin), (dx * sin + dy * cos)

    return dx, dy


@dataclasses.dataclass
class Blink:
  """Blink the drawing on and off."""
  on: float = 1.0        # Remain visible for this many seconds, then
  off: float = 0.0       # Go invisible for this long, then repeat
  t_offset: float = 0.0  # Offset the t_abs input by this amount

  def at(self, t_abs: float) -> bool:
    """Whether the object is visible at absolute time t_abs."""
    return (t_abs + self.t_offset) % (self.on + self.off) < self.on


@dataclasses.dataclass
class Drawing:
  """Container for information about one of the drawings to compose.

  See module-level docstring for more information on these elements.
  """
  filename: str
  transform: str = ''
  start: float = 0.0
  end: float = 1.0
  path: Path | None = None
  rose: Rose | None = None
  blink: Blink | None = None
  lines: str = ''

  _orig_x: float | None = None
  _orig_y: float | None = None

  def transform_at(self, t_abs: float, t_rel: float) -> str:
    """Retrieve a -t flag directive for this drawing at a specific time

    Args:
      t_abs: Absolute time in seconds since the start of the animation.
      t_rel: Progress through the animation --- a value in [0, 1].

    Returns:
      A hpgl2tek.py -t flag directive as described.
    """
    if not self.start <= t_rel <= self.end: raise ValueError(
        f'Lifespan for {self.filename} is {self.start}..{self.end}, but '
        f'there was an attempt to draw it at relative position {t_rel}')
    transform_parts = [self.transform] if self.transform else []

    # sorry, this is some post-hoc caching nonsense! but this is a
    # speed-critical section.
    if self._orig_x is None:
      self._set_origs()

    # Apply programmed motions if specified.
    x, y = self._orig_x, self._orig_y
    assert x is not None  # mypy
    assert y is not None
    if self.path is not None:
      x, y = self.path.at(
          (t_rel - self.start)/(self.end - self.start or math.inf))
    if self.rose is not None:
      dx, dy = self.rose.at(t_abs)
      x += dx
      y += dy
    if x != self._orig_x or y != self._orig_y:
      transform_parts.append(f'x{x}!y{y}')

    return '!'.join(transform_parts)

  def _set_origs(self):
    """Analyse the transform spec; determine x, y drawing location."""
    self._orig_x = self._orig_y = 0.0
    for part in (p.strip() for p in self.transform.split('!')):
      if part.startswith('x'):
        self._orig_x = float(part[1:])
      if part.startswith('y'):
        self._orig_y = float(part[1:])


class OriginShiftError(RuntimeError):
  """For signalling that origin shifting pushed drawn points off the screen."""


@dataclasses.dataclass
class Animation:
  """Container for all of the information about an animation."""
  drawings: dict[str, Drawing] = dataclasses.field(default_factory=dict)
  fps: float = 25.0
  duration: float = 5.0
  r12_origin_shift: tuple[int, int] = (0, 0)

  def process_config(self, config: configparser.ConfigParser):
    """Fill in Animation properties from a parsed config file."""
    # First, copy in basic values.
    animation = config['animation']
    self.fps = animation.getfloat('fps')
    self.duration = animation.getfloat('duration')

    # Collect drawings.
    for key in (k for k in config if k not in ('animation', 'DEFAULT')):
      drawing_config = config[key]
      # Basic configuration first. Everything's optional except for the file.
      drawing_kwargs: dict = {'filename': drawing_config['file']}
      if 'transform' in drawing_config:
        drawing_kwargs['transform'] = drawing_config['transform']
      if 'start' in drawing_config:
        drawing_kwargs['start'] = drawing_config.getfloat('start')
      if 'end' in drawing_config:
        drawing_kwargs['end'] = drawing_config.getfloat('end')

      # A motion path, if specified.
      if 'path' in drawing_config:
        control_points = []
        parts = (p for p in drawing_config['path'].strip().split(' ') if p)
        for part in parts:
          x, y = part.split(',')
          control_points.append((float(x), float(y)))
        drawing_kwargs['path'] = Path(tuple(control_points))

      # A rose perturbation, if specified.
      if 'rose' in drawing_config:
        rose_kwargs: dict[str, float] = {}
        for command in (c.strip() for c in drawing_config['rose'].split(' ')):
          if not command:
            continue
          if command.startswith('k'):
            rose_kwargs['k'] = float(command[1:])
          elif command.startswith('nu'):
            rose_kwargs['nu'] = float(command[2:])
          elif command.startswith('sx'):
            rose_kwargs['stretch_x'] = float(command[2:])
          elif command.startswith('sy'):
            rose_kwargs['stretch_y'] = float(command[2:])
          elif command.startswith('r'):
            rose_kwargs['rotate'] = float(command[1:]) * math.pi / 180.0
          elif command.startswith('dt'):
            rose_kwargs['t_offset'] = float(command[2:])
        drawing_kwargs['rose'] = Rose(**rose_kwargs)

      # Blinking behaviour, if specified.
      if 'blink' in drawing_config:
        blink_kwargs: dict[str, float] = {}
        args = [float(a) for a in drawing_config['blink'].split(',')]
        blink_kwargs['on'], blink_kwargs['off'] = args[:2]
        if len(args) > 2:
          blink_kwargs['t_offset'] = args[2]
        drawing_kwargs['blink'] = Blink(**blink_kwargs)

      # More lines to draw.
      if 'lines' in drawing_config:
        drawing_kwargs['lines'] = drawing_config['lines']

      self.drawings[key] = Drawing(**drawing_kwargs)

  def at(self, t_abs: float) -> hpgl2tek.Strokes:
    """Construct hpgl2tek.py strokes for time absolute time t."""
    # Compute normalised time in [0, 1], covering the animation's duration.
    if not 0 <= t_abs <= self.duration: raise ValueError(
        f'Value {t_abs=} not in [0, {self.duration}]')
    t_rel = t_abs / self.duration

    # Collect drawings that are visible right now.
    t_drawings = []
    for drawing in self.drawings.values():
      if drawing.blink is None or drawing.blink.at(t_abs):
        if drawing.start <= t_rel <= drawing.end:
          t_drawings.append(drawing)

    # Collect drawing filenames and drawing transformations.
    t_filenames = [d.filename for d in t_drawings]
    t_transforms = [d.transform_at(t_abs, t_rel) for d in t_drawings]
    t_transforms = [f'{i}:{x}' for i, x in enumerate(t_transforms)]
    t_lines = [d.lines for d in t_drawings if d.lines]

    # Open HPGL files; assemble strokes and drawing commands.
    with contextlib.ExitStack() as stack:
      files = [stack.enter_context(open(fn, 'r')) for fn in t_filenames]
      transforms = ','.join(t_transforms)
      lines = ','.join(t_lines)
      strokes = hpgl2tek.get_all_strokes(files, transforms, lines)
    return strokes

  def animate_to_r12zip(
      self,
      file_number: int,
      automate_delay: float,
      monitor_pipe: BinaryIO | None
  ) -> bytes:
    """Construct a ZIP archive of animation files for a Tek computer with R12.

    Renders the animation into a ZIP file containing files to load onto a
    Flash Drive device (or a real physical tape somehow) and play on a
    Tektronix 4050-series machine with the R12 "fast graphics" ROM pack
    installed.

    Args:
      file_number: Tape record number of the first file in the archive, which
          is the BASIC program that displays the animations. If this number is
          8, for example, then you would load this program by seeking the tape
          (or the Flash Drive) to file 8 and then OLDing it in. Must be non-
          negative.
      automate_delay: If 0, then the BASIC program halts after displaying each
          frame; to show the next frame, press user-defined key 1. If greater
          than 0, the BASIC program prints the string "AAAA" to GPIB address
          @53 (intending to send the string out of the Option 10 printer
          interface --- you should rig up something to the interface so that
          this clicks your camera shutter), then waits this many seconds
          before clearing the screen and automatically moving on to the next
          frame (requiring the TransEra 741 RTC module). A value of 2.0 works
          for this program's author.
      monitor_pipe: An optional BinaryIO handle that ought to terminate in a
          device that can interpret and display Tektronix 4010 graphics
          commands. You can use this to watch the animation as it is being
          rendered.

    Returns:
      The contents of the ZIP archive built by this method, suitable for
      writing to a file.
    """
    n = file_number  # Abbreviation.
    num_frames = int(self.duration * self.fps)
    seconds_per_frame = 1 / self.fps

    # Prepare the BASIC program to draw the animation.
    automated = automate_delay > 0.0
    basic = bytes('\r'.join([
        '1 GO TO 100',
        '4 GO TO 130',
        '100 INIT',
        '110 DIM S$(8190)',
       f'120 LET F={n}',
        '130 F=F+1',
       f'140 IF F>{n + num_frames} THEN 240',
        '150 FIND@5:F',
        '160 PAGE',
        '170 READ@5:S$',
       f'180 IF S$="X" THEN {"210" if automated else "260"}',
        '190 CALL "RDRAW",S$,1,0,0',
        '200 GO TO 170',
       f'210 {"" if automated else "REM "} PRINT @53:"AAAA"',
       f'220 {"" if automated else "REM "} CALL "!PAUSE",{automate_delay}',
        '230 GO TO 130',
        '240 HOME',
        '250 PRINT "No more frames"',
        '260 END ', '', '']),  # Ending with space-CR-CR seems common.
        encoding='ascii')
    # Tape filename for the BASIC program.
    fn_basic = f'{n:<7}ASCII   PROG Animation player {len(basic)}'

    # We'll start packing data into a zip file. We won't bother compressing.
    zipdata = io.BytesIO()
    with zipfile.ZipFile(zipdata, "a") as zf:
      zf.writestr(fn_basic, basic)

      # Now to make the indivdual animation frames.
      for frame in range(num_frames):
        t_abs = frame * seconds_per_frame
        strokes = self._apply_r12_origin_shift(self.at(t_abs))
        r12_commands = hpgl2tek.strokes_to_tek4050r12(strokes)
        r12_image = hpgl2tek.tek4050r12_to_tape_records(r12_commands)
        k = n + frame + 1
        fn_frame = f'{k:<7}BINARY  DATA Frame {frame:<5}      {len(r12_image)}'
        zf.writestr(fn_frame, r12_image)

        # Show the frame on the monitor if one is available.
        self._show_on_monitor(strokes, monitor_pipe)

    # Return the final zip file data.
    return zipdata.getvalue()

  def animate_to_video(self, monitor_pipe: BinaryIO | None) -> bytes:
    """Construct an MP4 video of the animation in stylish green-on-black.

    Renders the animation into a 1024x780 MP4 video.

    Args:
      monitor_pipe: An optional BinaryIO handle that ought to terminate in a
          device that can interpret and display Tektronix 4010 graphics
          commands. You can use this to watch the animation as it is being
          rendered.

    Returns:
      MP4 video data suitable for writing to a file.
    """
    num_frames = int(self.duration * self.fps)
    seconds_per_frame = 1 / self.fps

    # Prepare OpenCV's video writer and a temporary directory where the created
    # video file will live.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tempdir:
      fourcc = cv2.VideoWriter_fourcc(*'mp4v')
      tempfilename = os.path.join(tempdir, 'video.mp4')
      videowriter = cv2.VideoWriter(
          tempfilename, fourcc, self.fps, (1024, 780))

      # Render individual animation frames and add to the video.
      for frame in range(num_frames):
        t_abs = frame * seconds_per_frame
        strokes = self.at(t_abs)
        pil_image = hpgl2tek.strokes_to_pil_image(strokes)
        videowriter.write(np.array(pil_image))

        # Show the frame on the monitor if one is available.
        self._show_on_monitor(strokes, monitor_pipe)

      # Close video writer and load video data, then return the data.
      videowriter.release()
      with open(tempfilename, 'rb') as f:
        return f.read()

  def _apply_r12_origin_shift(
      self,
      strokes: hpgl2tek.Strokes,
  ) -> hpgl2tek.Strokes:
    if self.r12_origin_shift == (0, 0):
      return strokes
    else:
      dx, dy = self.r12_origin_shift
      new_strokes: hpgl2tek.Strokes = []
      for stroke in strokes:
        new_stroke: hpgl2tek.Stroke = []
        for x, y in stroke:
          if not (0 < (nx := x + dx) < 1023 and 0 < (ny := y + dy) < 780):
            raise OriginShiftError(
                f'Origin shift displacement of {self.r12_origin_shift} has '
                f'pushed a point at {(x, y)} out-of-bounds.')
          else:
            new_stroke.append((nx, ny))
        new_strokes.append(new_stroke)
      return new_strokes

  def _show_on_monitor(
      self,
      strokes: hpgl2tek.Strokes,
      monitor_pipe: BinaryIO | None
  ):
    if monitor_pipe is not None:
      t4010_image = hpgl2tek.strokes_to_tek4010(strokes)
      monitor_pipe.write(b'\x1b\x0c')  # Clear ("page") the screen.
      monitor_pipe.write(t4010_image)
      monitor_pipe.flush()


@contextlib.contextmanager
def monitor() -> Iterator[BinaryIO]:
  """Spawn a "monitor" window as a context manager.

  A monitor window is an xterm in Tektronix mode that prints whatever you
  emit into the returned file handle, including all control characters, drawing
  commands, etc.

  Yields:
    A file handle as described above.
  """
  # Check it out: a nested context manager that owns the xterm window process:
  @contextlib.contextmanager
  def monitor_xterm(pipename: str):
    process = subprocess.Popen([
        XTERM, '-t', '-fg', 'green', '-e', f'{CAT} {pipename}'])
    yield
    process.kill()

  # Now down to business. First, make a private temporary directory.
  tempdir = tempfile.mkdtemp()

  # Try to make a named pipe in the directory.
  pipename = os.path.join(tempdir, 'pipe')
  try:
    os.mkfifo(pipename)
  except OSError as e:
    print('Failed to create named pipe: {e}', file=sys.stderr)
  else:
    # Try to spawn the xterm window now listening to the named pipe.
    with monitor_xterm(pipename):
      # Since there should be a listener now on the other side of the named
      # pipe, it's safe to just open the named pipe for writing: we shouldn't
      # hang unless the xterm prematurely dies. In which case, oh well.
      with open(pipename, 'wb') as f:
        yield f

  # Try to remove the temporary directory and its contents; ignore failures.
  finally:
    for item in [pipename]:
      try:
        os.remove(item)
      except:
        pass
    try:
      os.rmdir(tempdir)
    except:
      pass


@contextlib.contextmanager
def optional_monitor(want_monitor: bool) -> Iterator[BinaryIO | None]:
  """A monitor() wrapper that spawns a monitor only if want_monitor is True.

  Args:
    want_monitor: Whether the caller wants a monitor.

  Returns:
    A binary file output handle if a monitor was requested; None otherwise.
  """
  if want_monitor:
    with monitor() as pipe:
      yield pipe
  else:
    yield None


def main(FLAGS: argparse.Namespace):
  # 10 RANDOMIZE TIMER (repeatably)
  random.seed(FLAGS.animation_file.name)

  # Read in the config.
  config = configparser.ConfigParser()
  config.read_file(FLAGS.animation_file)

  # Keep trying to animate with various origin shifts until one actually works.
  # Horrid, I know, but the hack only has to work once.
  # TODO: Replace with code that calculates viable origin shifting range and
  # selects a random point within. Too busy to do that right now.
  while True:
    try:
      animation = Animation(r12_origin_shift=(
          tuple(random.choices(range(-4, 4), k=2)  # type: ignore
          if FLAGS.origin_shift else (0, 0))))
      animation.process_config(config)

      # Render the animation as directed, optionally monitoring it in an xterm.
      with optional_monitor(FLAGS.monitor) as pipe:
        # For 4050 ZIP file outputs:
        if FLAGS.device == 'tek4050r12zip':
          if FLAGS.file_number is None: raise RuntimeError(
              'A --file_number argument is required for --device=tek4050r12zip')
          data = animation.animate_to_r12zip(
              FLAGS.file_number, FLAGS.automate, pipe)
        # For modern video outputs:
        elif FLAGS.device == 'video':
          data = animation.animate_to_video(pipe)
        else:
          raise RuntimeError(f'Unknown --device selection "{FLAGS.device}"')

      # If we got here, the animation has successfully completed.
      break

    except OriginShiftError as e:
      # If we got here, an origin shift failure has occurred. Print it out and
      # try a different origin shift (yuck).
      print(f'{e}')

  # Save the animation output
  FLAGS.output.buffer.write(data)


if __name__ == '__main__':
  flags = _define_flags()
  FLAGS = flags.parse_args()
  main(FLAGS)
