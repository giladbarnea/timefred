import os
from typing import Optional, Iterable, Union, Any, Type, Mapping

from timefred import color as c
from timefred.color import Colored, TaskString
from timefred.integration.jira import JiraTicket
from timefred.note import Note
from timefred.space import AttrDictSpace, Field, TypedListSpace, DefaultAttrDictSpace
from timefred.tag import Tag
from timefred.time import XArrow, Timespan
from timefred.time.timeutils import secs2human
from timefred.util import normalize_str


class Entry(AttrDictSpace):
    start: XArrow = Field(cast=XArrow.from_absolute)
    end: Optional[XArrow] = Field(optional=True, cast=XArrow.from_absolute)
    notes: Optional[list[Note]] = Field(optional=True, cast=list[Note])
    tags: Optional[set[Tag]] = Field(optional=True, cast=list[Tag])
    
    # @Field(optional=True)
    @property
    def timespan(self):
        start = self.start
        end = self.end
        timespan = Timespan(start=start, end=end)
        return timespan
    
    # def __init__(self, name, start, end=None, notes=None, tags=None, jira=None) -> None:
    # 	super().__init__(dict(name=name,
    # 						  start=start,
    # 						  end=end,
    # 						  notes=notes or [],
    # 						  tags=tags or set(),
    # 						  jira=jira))
    
    # @property
    # def notes(self) -> list[Note]:
    # 	if self.__cache__.notes:
    # 		return self._notes
    # 	for i, note in enumerate(self._notes):
    # 		if not isinstance(note, Note):
    # 			self._notes[i] = Note(note)
    # 	self.__cache__.notes = True
    # 	return self._notes
    
    # @property
    # def start(self) -> XArrow:
    # 	if self._start and not isinstance(self._start, Arrow):
    # 		self._start = XArrow.from_formatted(self._start)
    # 	return self._start
    
    # @start.setter
    # def start(self, val):
    # 	self._start = val
    
    # @property
    # def end(self) -> XArrow:
    # 	if self._end and not isinstance(self._end, Arrow):
    # 		self._end = XArrow.from_formatted(self._end)
    # 	return self._end
    #
    # @end.setter
    # def end(self, val):
    # 	self._end = val


class Activity(TypedListSpace[Entry], default_factory=Entry):
    """Activity (name=..., jira=...) [Entry, Entry...]"""
    name: Colored = Field(cast=TaskString)
    jira: Optional[JiraTicket] = Field(default_factory=JiraTicket)
    
    def __init__(self, iterable: Iterable = (), **kwargs) -> None:
        # Necessary because otherwise TypedSpace.__new__ expects (self, default_factory, **kwargs)
        super().__init__(iterable, **kwargs)
    
    def __repr__(self) -> str:
        name = f'{getattr(self, "name")}'
        short_id = f'{str(id(self))[-4:]}'
        jira = self.jira
        representation = f'{self.__class__.__qualname__} ({name=!r}, {jira=!r} <{short_id}>) {list.__repr__(self)}'
        return representation
    
    def shortrepr(self) -> str:
        """Like repr, but with only the last entry."""
        name = f'{getattr(self, "name")}'
        short_id = f'{str(id(self))[-4:]}'
        jira = self.jira
        last_entry = self.safe_last_entry()
        self_len = len(self)
        if self_len > 1:
            short_entries_repr = f'[... {last_entry}]'
        elif self_len == 1:
            short_entries_repr = f'[{last_entry}]'
        else:
            short_entries_repr = f'[]'
        representation = f'{self.__class__.__qualname__} ({name=!r}, {jira=!r} <{short_id}>) {short_entries_repr}'
        return representation
    
    def safe_last_entry(self) -> Optional[Entry]:
        try:
            return self[-1]
        except IndexError:
            return None
    
    # @multimethod
    # def has_similar_name(self, other: 'Entry') -> bool:
    #     return self.has_similar_name(other.name)
    #
    # @multimethod
    def has_similar_name(self, other: str) -> bool:
        """Compares the activity's lowercase, stripped and non-word-free name to other."""
        return normalize_str(self.name) == normalize_str(other)
    
    def ongoing(self) -> bool:
        last_entry = self.safe_last_entry()
        return bool(last_entry and not last_entry.end)
    
    def stop(self,
             time: Union[str, XArrow] = None,
             tag: Union[str, Tag] = None,
             note: Union[str, Note] = None) -> Entry:
        """
        Returns:
            Last entry.
        Raises:
            ValueError: if the activity is not ongoing
        """
        last_entry = self.safe_last_entry()
        if not last_entry or last_entry.end:
            raise ValueError(f'{self.shortrepr()} is not ongoing')
        if not time:
            time = XArrow.now()
        if last_entry.start > time:
            raise ValueError(f'Cannot stop {self.shortrepr()} before start time (tried to stop at {time!r})')
        last_entry.end = time
        
        if tag:
            last_entry.tags.add(tag)
        if note:
            last_entry.notes.append(note)
        return last_entry
    
    def start(self,
              time: Union[XArrow, str] = None,
              tag: Union["Tag", str] = None,
              note=None) -> Entry:
        """
        Raises:
            ValueError: if the activity is ongoing
        """
        if self.ongoing():
            raise ValueError(f'{self.shortrepr()} is already ongoing')
        entry = Entry(start=time)
        if tag:
            entry.tags.add(tag)
        if note:
            entry.notes.append(note)
        
        self.append(entry)
        return entry

    def timespans(self) -> list[Timespan]:
        return sorted(map(lambda entry: entry.timespan, self))

    def seconds(self) -> int:
        return sum(self.timespans())

    def human_duration(self) -> str:
        return secs2human(self.seconds())

    def pretty(self, detailed: bool = True, width: int = 24):
        timespans = self.timespans()
        if detailed:
            time = "\n  \x1b[2m"
            notes = []
            [notes.extend(filter(bool, entry.notes)) for entry in self]
            if notes:
                time += '\n  ' + c.grey150('Times')
        
            for start, end in timespans:
                if end:
                    time += f'\n  {start.HHmmss} → {end.HHmmss} ({end - start})'
                else:
                    time += f'\n  {start.HHmmss}'
        
            if notes:
                time += '\n\n  ' + c.grey150('Notes')
        
            # for note_time, note_content in sorted(log_entry.notes, key=lambda _n: _n[0] if _n[0] else '0'):
            for note_content, note_time in filter(bool, notes):
                if note_time:
                    time += f'\n  {note_content} ({note_time.HHmmss})'
                else:
                    time += f'\n  {note_content}'
        
            time += "\x1b[0m\n"
        else:
            # earliest_start_time = self.earliest_start()
            earliest_start_time = timespans[0].start
            time = c.i(c.dim('   started ' + earliest_start_time.HHmmss))
    
        if self.ongoing():
            name = c.title(self.name)
        else:
            name = c.w200(self.name)
    
        if detailed:
            tags = set()
            [tags.update(set(filter(bool, entry.tags))) for entry in self]
            name += f'  {", ".join(c.dim(c.tag2(_tag)) for _tag in tags)}'
    
        pretty = ' '.join([c.ljust_with_color(name, width),
                           '\x1b[2m\t\x1b[0m ',
                           self.human_duration(),
                           time])
        return pretty


class Day(DefaultAttrDictSpace[Any, Activity], default_factory=Activity):
    """Day { "activity_name": Activity }"""
    __default_factory__: Type[Activity]
    
    def __getitem__(self, name):
        # log(f'[title]{self.__class__.__qualname__}.__getitem__({name!r})...')
        try:
            # Don't want the whole DefaultAttrDictSpace->DefaultDictSpace->TypedDictSpace.__getitem__(name) flow,
            # because we want self.__default_factory__(name=name), and TypedDictSpace does self.__default_factory__()
            item = dict.__getitem__(self, name)
            # item = super(AttrDictSpace).__getitem__(self, name)
            
            # AttributeError: 'super' object has no attribute '__getitem__' error
            # item = super(dict, self).__getitem__(name)
            
            # AttributeError: 'super' object has no attribute '__getitem__' error
            # item = super(dict, self.__class__).__getitem__(name)
            
            # constructed = self.__dict__[name]
        except KeyError as e:
            # log(f'  KeyError: {e}',
            #     f'self.__dict__.get({name!r}) = {self.__dict__.get(name)}',
            #     f'self.get({name!r}, UNSET) = {self.get(name, UNSET)}',
            #     sep='\n  ')
            # log(f'  constructed = self.__default_factory__(name={name!r})')
            constructed = self.__default_factory__(name=name)
            # log(f'  {constructed = !r} | {constructed.name = !r}')
            # assert constructed.name == name, f'{constructed.name = !r}, {name = !r}'
            # log(f'  setattr(self, {name!r}, {constructed!r})')
            setattr(self, name, constructed)
        else:
            # log(f'  No KeyError',
            #     f'{item = !r}',
            #     f'self.__dict__.get({name!r}) = {self.__dict__.get(name)}',
            #     f'self.get({name!r}, UNSET) = {self.get(name, UNSET)}',
            #     f'{isinstance(item, self.__default_factory__) = }',
            #     f'{item = !r}',
            #     f'{getattr(item, "name", UNSET) = !r}',
            #     sep='\n  ')
            if isinstance(item, self.__default_factory__):
                constructed = item
            else:
                assert not isinstance(item, Mapping)  # because __default_factory__ expects pos arg, not **mapping
                constructed = self.__default_factory__(item, name=name)
                # assert constructed.name == name, f'{constructed.name=!r} != {name=!r} ({self.__class__.__qualname__})'
                setattr(self, name, constructed)
        # assert constructed.name == name, f'{constructed.name=!r} != {name=!r} ({self.__class__.__qualname__})'
        # log(f'{self.__class__.__qualname__}.__getitem__({name!r}) => {constructed!r}\n\n')
        return constructed

    def seconds(self) -> int:
        return sum(map(lambda activity: activity.seconds(), self.values()))

    def human_duration(self) -> str:
        return secs2human(self.seconds())

class Work(DefaultAttrDictSpace[Any, Day], default_factory=Day):
    """Work { "31/10/21": Day }"""
    __default_factory__: Type[Day]
    
    def ongoing_activity(self) -> Activity:
        """
        Raises:
            ValueError: if there is no ongoing activity
        """
        # TODO: cache somehow
        for ddmmyy in reversed(self.keys()):
            day = self[ddmmyy]  # invoke __getitem__ to get constructed Day
            for name in reversed(day.keys()):
                activity = day[name]
                if activity.ongoing():
                    return activity
        raise ValueError(f'No ongoing activity')
    
    def stop(self,
             time: Union[str, XArrow] = None,
             tag: Union[str, Tag] = None,
             note: Union[str, Note] = None) -> Optional[Activity]:
        """
        Raises:
            ValueError: if there is no ongoing activity
        """
        ongoing_activity = self.ongoing_activity()
        if not time:
            time = XArrow.now()
        ongoing_activity.stop(time=time, tag=tag, note=note)
        stopped_activity = ongoing_activity
        return stopped_activity
    
    def on(self,
           name: Union[str, Activity],
           time: Union[str, XArrow] = None,
           tag: Union[str, Tag] = None,
           note: Union[str, Note] = None) -> Activity:
        """
        Raises:
            ValueError: if an activity with the same / similar name is already ongoing
        """
        if time is None:
            time = XArrow.now()
        try:
            ongoing_activity = self.ongoing_activity()
        except ValueError:
            # No ongoing activity -> start new activity
            day = self[time.DDMMYY]
            activity: Activity = day[name]
            activity.start(time, tag, note)
            return activity
        else:
            # Ongoing activity -> stop it and start new activity
            if name == ongoing_activity.name:
                raise ValueError(f'{ongoing_activity.shortrepr()} is already ongoing')
            if ongoing_activity.has_similar_name(name):
                raise ValueError(f'{ongoing_activity.shortrepr()} is ongoing, and has a similar name to {name!r}')
            ongoing_activity.stop(time)
            day = self[time.DDMMYY]
            activity: Activity = day[name]
            activity.start(time, tag, note)
            return activity


if os.getenv('TIMEFRED_BIRDSEYE'):
    import cheap_repr
    
    cheap_repr.register_repr(Activity)(cheap_repr.normal_repr)

assert Day.__default_factory__ == Activity

assert Work.__default_factory__ == Day
assert Day.__default_factory__ == Activity
assert Work.__default_factory__ == Day
assert Day.__default_factory__ == Activity
