import re
from multimethod import multimethod

from timefred import color as c
from timefred.space import DictSpace, Field
from timefred.time.xarrow import XArrow
from timefred.util import normalize_str

NOTE_TIME_RE = re.compile(r'(.+) \(([\d/: ]+)\)', re.IGNORECASE)


class Note(DictSpace):
	time: XArrow = Field(default_factory=XArrow.from_absolute, cast=XArrow)
	content: str = Field(default_factory=str)
	
	# def __new__(cls, note: Mapping) -> "Note":
	# 	time = next(iter(note))
	# 	content = note[time]
	# 	instance = super().__new__(cls, time=time, content=content)
	# 	return instance
	
	# @multimethod
	# def __init__(self, content: str, time: Union[str, XArrow]=None):
	# 	self.content = content
	# 	if not time:
	# 		time = XArrow.now()
	# 	self._time = time
	#
	# @multimethod
	# def __init__(self, note: str):
	# 	match = NOTE_TIME_RE.fullmatch(note)
	# 	if match:
	# 		match_groups = match.groups()
	# 		self.content = match_groups[0]
	# 		self._time = match_groups[1]
	# 	else:
	# 		self.content = note
	# 		self._time = None

	def __iter__(self):
		yield self.content
		yield self.time

	def __bool__(self):
		return bool(self.content)

	def __repr__(self) -> str:
		if self.time:
			return f'{self.content} ({self.time.HHmmss})'
		return self.content

	def pretty(self):
		content_bold = c.b(self.content)
		if self.time:
			return c.note(f'{content_bold} ({self.time.HHmmss})')
		return c.note(content_bold)

	# @property
	# def time(self) -> XArrow:
	# 	if self._time and not isinstance(self._time, Arrow):
	# 		self._time = XArrow.from_formatted(self._time)
	# 	return self._time

	@multimethod
	def is_similar(self, other: "Note") -> bool:
		return self.is_similar(other.content)

	@multimethod
	def is_similar(self, other: str) -> bool:
		other_normalized = normalize_str(other)
		self_normalized = normalize_str(self.content)

		return self_normalized in other_normalized or other_normalized in self_normalized
