# coding: utf-8

"""
ti is a simple and extensible time tracker for the command line. Visit the
project page (http://ti.sharats.me) for more details.

Usage:
  ti (o|on) <name> [<start time>...]
  ti (f|fin) [<end time>...]
  ti (s|status)
  ti (t|tag) <tag>...
    Add tag to current activity, e.g `ti tag red for-joe`.
  ti (n|note) <note-text>...
    `ti note Discuss this with the other team.`
  ti (l|log) [today]
  ti (e|edit)
  ti (i|interrupt)
    Marks end time of current activity, pushes it to interrupt stack, and starts an "interrupt" activity.
  ti --no-color
  ti -h | --help

Options:
  -h --help         Show this help.
  <start-time>...   A time specification (goto http://ti.sharats.me for more on
                    this).
  <tag>...          Tags can be made of any characters, but its probably a good
                    idea to avoid whitespace.
  <note-text>...    Some arbitrary text to be added as `notes` to the currently
                    working project.
"""

import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta

import yaml

from ti import times
from ti.color import yellow, green, red, strip_color, ljust_with_color
from ti.error import TIError, NoEditor, InvalidYAML, NoTask, BadArguments
from ti.store import Store
from ti.times import human2dt, formatted2dt, timegap, human2formatted, secs2human


def on(name, time):
    data = store.load()
    work = data['work']

    if work and 'end' not in work[-1]:
        ok = fin(time)
        if ok:
            return on(name, time)
        return False

    entry = {
        'name':  name,
        'start': time,
        }

    work.append(entry)
    store.dump(data)

    print('Start working on ' + green(name) + f' at {time}.')


def fin(time, back_from_interrupt=True):
    ensure_working()

    data = store.load()

    current = data['work'][-1]
    current['end'] = time
    ok = store.dump(data)
    print('So you stopped working on ' + red(current['name']) + f' at {time}.')
    if not ok:
        return False
    if back_from_interrupt and len(data['interrupt_stack']) > 0:
        name = data['interrupt_stack'].pop()['name']
        store.dump(data)
        on(name, time)
        if len(data['interrupt_stack']) > 0:
            print('You are now %d deep in interrupts.'
                  % len(data['interrupt_stack']))
        else:
            print("Congrats, you're out of interrupts!")
    return True


def interrupt(name, time):
    ensure_working()

    fin(time, back_from_interrupt=False)

    data = store.load()
    if 'interrupt_stack' not in data:
        data['interrupt_stack'] = []
    interrupt_stack = data['interrupt_stack']

    interrupted = data['work'][-1]
    interrupt_stack.append(interrupted)
    store.dump(data)

    on('interrupt: ' + green(name), time)
    print('You are now %d deep in interrupts.' % len(interrupt_stack))


def note(content):
    ensure_working()
    now = human2formatted(fmt="%X")
    content += f' ({now})'
    data = store.load()
    current = data['work'][-1]

    if 'notes' not in current:
        current['notes'] = [content]
    else:
        current['notes'].append(content)

    store.dump(data)

    print(f'Noted "\x1b[3m{content}\x1b[0m" to ' + yellow(current['name']) + '.')


def tag(tags):
    ensure_working()

    data = store.load()
    current = data['work'][-1]

    current['tags'] = set(current.get('tags') or [])
    current['tags'].update(tags)
    current['tags'] = list(current['tags'])

    store.dump(data)

    tag_count = len(tags)
    print(f"Okay, tagged current work with {tag_count:d} tag{'s' if tag_count > 1 else ''}.")


def status(show_notes=False):
    ensure_working()

    data = store.load()
    current = data['work'][-1]

    start_time = formatted2dt(current['start'])
    diff = timegap(start_time, datetime.now())

    notes = current.get('notes')
    if not show_notes or not notes:
        print(f'You have been working on {green(current["name"])} for {green(diff)}.')
        return
    try:
        from rich import print as rprint
    except ModuleNotFoundError:
        rprint = print
    rprint('\n    '.join([f'You have been working on [green]{current["name"]}[/] for [green]{diff}[/].\nNotes:[rgb(170,170,170)]',
                          *[f'[rgb(100,100,100)]o[/rgb(100,100,100)] {n}' for n in notes],
                          '[/]']))


def log(period, *, detailed=False):
    data = store.load()
    work = data['work'] + data['interrupt_stack']
    _log = defaultdict(lambda: {'duration': timedelta(), 'times': []})
    current = None
    period_dt = human2dt(period)
    if not period_dt:
        breakpoint()
    now = datetime.now()
    for item in work:
        start_time = formatted2dt(item['start'])
        if period and period_dt.day != start_time.day:
            continue
        end_time = item.get('end') and formatted2dt(item['end'])
        _log[item['name']]['times'].append((start_time, end_time))

        if end_time:
            _log[item['name']]['duration'] += end_time - start_time
        else:
            _log[item['name']]['duration'] += now - start_time
            current = item['name']
    name_col_len = 0
    total_secs = 0
    for name, item in _log.items():
        name_col_len = max(name_col_len, len(strip_color(name)))

        secs = int(item['duration'].total_seconds())
        total_secs += secs
        pretty = secs2human(secs)
        _log[name]['pretty'] = pretty

    if len(period) > 2:
        title = period.title()
    else:
        title = f"{period[0]} {times.ABBREVS[period[1]]} ago"
    try:
        from rich import print as rprint
    except ModuleNotFoundError:
        rprint = print
    rprint(f"[b bright_white]{title}'s logs:[/]" + '\n' if detailed else '')

    for name, item in sorted(_log.items(), key=lambda entry: min(map(lambda t: t[0], entry[1]['times']))):
        if detailed:
            start_end_times = item["times"]
            time = "\n  \x1b[2m"
            for start, end in start_end_times:
                if end:
                    time += f'\n  {start.strftime("%X")} − {end.strftime("%X")} ({end - start})'
                else:
                    time += f'\n  {start.strftime("%X")}'
            time += "\x1b[0m\n"
        else:
            fist_start_time = min(map(lambda t: t[0], item["times"]))
            time = f'\x1b[2mstarted: {fist_start_time.strftime("%X")}\x1b[0m'

        if current == name:
            name = f'\x1b[1m{name}\x1b[0m'

        print(ljust_with_color(name, name_col_len),
              ' ∙∙ ',
              item['pretty'],
              time)

    rprint(f"[b bright_white]Total:[/] {secs2human(total_secs)}")


def edit():
    if "EDITOR" not in os.environ:
        raise NoEditor("Please set the 'EDITOR' environment variable")

    data = store.load()
    yml = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)

    cmd = os.getenv('EDITOR')
    fd, temp_path = tempfile.mkstemp(prefix='ti.')
    with open(temp_path, "r+") as f:
        f.write(yml.replace('\n- ', '\n\n- '))
        f.seek(0)
        subprocess.check_call(cmd + ' ' + temp_path, shell=True)
        yml = f.read()
        f.truncate()

    os.close(fd)
    os.remove(temp_path)

    try:
        data = yaml.load(yml)
    except:
        raise InvalidYAML("Oops, that YAML doesn't appear to be valid!")

    store.dump(data)


def is_working():
    data = store.load()
    return data.get('work') and 'end' not in data['work'][-1]


def ensure_working():
    if is_working():
        return

    raise NoTask("For all I know, you aren't working on anything.")


def parse_args(argv=sys.argv):
    # prog = argv[0]
    if len(argv) == 1:
        raise BadArguments("You must specify a command.")

    head = argv[1]
    tail = argv[2:]

    if head in ['-h', '--help', 'h', 'help']:
        raise BadArguments()

    elif head in ['e', 'edit']:
        fn = edit
        args = {}

    elif head in ['o', 'on']:
        if not tail:
            raise BadArguments("Need the name of whatever you are working on.")

        fn = on
        name = tail.pop(0)
        time = human2formatted(' '.join(tail) if tail else 'now')
        args = {
            'name': name,
            'time': time,
            }

    elif head in ['f', 'fin']:
        fn = fin
        args = {'time': human2formatted(' '.join(tail) if tail else 'now')}

    elif head in ('s', 's+', 'status', 'status+'):
        fn = status
        args = {'show_notes': '+' in head}

    elif head in ('l', 'l+', 'log', 'log+'):
        fn = log
        args = {
            'period':   tail[0] if tail else 'today',
            'detailed': '+' in head
            }

    elif head in ['t', 'tag']:
        if not tail:
            raise BadArguments("Please provide at least one tag to add.")

        fn = tag
        args = {'tags': tail}

    elif head in ['n', 'note']:
        if not tail:
            raise BadArguments("Please provide some text to be noted.")

        fn = note
        args = {'content': ' '.join(tail)}

    elif head in ['i', 'interrupt']:
        if not tail:
            raise BadArguments("Need the name of whatever you are working on.")

        fn = interrupt
        name = tail.pop(0)
        args = {
            'name': name,
            'time': human2formatted(' '.join(tail) if tail else 'now'),
            }

    else:
        raise BadArguments("I don't understand %r" % (head,))

    return fn, args


def main():
    try:
        fn, args = parse_args()
        fn(**args)
    except TIError as e:
        msg = str(e) if len(str(e)) > 0 else __doc__
        print(msg, file=sys.stderr)
        sys.exit(1)


store = Store(os.getenv('SHEET_FILE', None) or
              os.path.expanduser('~/.ti-sheet.yml'))

if __name__ == '__main__':
    main()
