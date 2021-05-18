import typing
from typing import Callable
from abc import ABC, abstractmethod
import re

# Syntax ABC
class Node(ABC):
	@abstractmethod
	def __str__(self) -> str:
		pass

class Container(Node):
	def __init__(self, *items: typing.Sequence[Node]):
		if len(items) < 2:
			raise ValueError("must have at least two items")
		self.items = items
	def __str__(self) -> str:
		return '(' + self.sep().join((str(x) for x in self.items)) + ')'
	@staticmethod
	@abstractmethod
	def sep() -> str:
		pass
class Quantifier(Node):
	def __str__(self):
		return f'{self.item}{self.suffix()}'
	@staticmethod
	@abstractmethod
	def suffix() -> str:
		pass
class Leaf(Node):
	def __str__(self) -> str:
		return self.text

# Containers
class Alternation(Container):
	def __init__(self, *items: typing.Sequence[Node]):
		super().__init__(*items)
	@staticmethod
	def sep() -> str:
		return " | "
class Sequence(Container):
	def __init__(self, *items: typing.Sequence[Node]):
		super().__init__(*items)
	@staticmethod
	def sep() -> str:
		return " "

# Quantifiers
class Optional(Quantifier):
	def __init__(self, item: Node):
		self.item = item
	@staticmethod
	def suffix() -> str:
		return "?"
class ZeroOrMore(Quantifier):
	def __init__(self, item: Node):
		self.item = item
	@staticmethod
	def suffix() -> str:
		return "*"
class OneOrMore(Quantifier):
	def __init__(self, item: Node):
		self.item = item
	@staticmethod
	def suffix() -> str:
		return "+"

# Leaf
class Terminal(Leaf):
	def __init__(self, text: str, cls: typing.Optional[str] = None):
		self.text = text
		self.cls = cls or ''
class NonTerminal(Leaf):
	def __init__(self, text: str):
		self.text = text

# Parser
_class_char = r'(?:[^\[\]\\-]|\\[\[\]\\-]|\\x[\da-fA-F]{2}|\\u[\da-fA-F]{4}|\\U\{[\da-fA-F]{1,6}\})'

_whitespace = re.compile(r'\s+')
_identifier = re.compile(r"\w[\w.-]*")
_literal_sq = re.compile(r"\'(?:[^\'\\]|\\.)*\'")
_literal_dq = re.compile(r"\"(?:[^\"\\]|\\.)*\"")
_comment = re.compile(r'/\*(?:[^*/]|[^*]/|\*[^/])*\*/')
_regex = re.compile(r'/(?:[^/\\]|\\.)*/i?')
_class_builtin = re.compile(r'\\[DSWdsw]')
_class_item = re.compile(rf'{_class_char}(?:-(?:{_class_char}))?')

del _class_char

class Reader:
	def __init__(self, source: str):
		self.source = str(source)
		self.off = 0
	def read(self):
		alternation = self.readAlternation()
		if self.off < len(self.source):
			raise ValueError(self.error("error at %p: invalid character"))
		return alternation
	def readAlternation(self) -> Node:
		alternation = []
		while True:
			alternation.append(self.readSequence())
			if not self.readLiteral('|'):
				break
		if len(alternation) > 1:
			return Alternation(*alternation)
		elif len(alternation) == 1:
			return alternation[0]
		else:
			raise ValueError(self.error("error at %p: invalid character"))
	def readSequence(self) -> Node:
		sequence = []
		while True:
			if item := self.readItem():
				sequence.append(item)
			else:
				break
		if len(sequence) > 1:
			return Sequence(*sequence)
		elif len(sequence) == 1:
			return sequence[0]
		else:
			raise ValueError(self.error("error at %p: invalid character"))
	def readItem(self) -> Node:
		# read item
		if match := self.readMatch(_identifier):
			# identifier
			item = NonTerminal(match.group(0))
		elif match := self.readMatch(_literal_sq) or self.readMatch(_literal_dq):
			# literal
			item = Terminal(match.group(0), cls="literal")
		elif match := self.readMatch(_comment):
			# comment
			return Terminal(match.group(0), cls="comment")
		elif match := self.readMatch(_regex):
			# regex
			item = Terminal(match.group(0), cls="regex")
		elif item := self.readClass():
			pass
		elif self.readLiteral('.'):
			# "any" char class
			item = Terminal('.', cls="char-class")
		elif self.readLiteral('('):
			# group
			item = self.readAlternation()
			if not item:
				raise ValueError(self.error("error at %p: expecting alternation after '('"))
			if not self.readLiteral(')'):
				raise ValueError(self.error("error at %p: expecting closing brace ')'"))
		else:
			# no next item
			return None
		# read quantifier
		if self.readLiteral('?'):
			item = Optional(item)
		elif self.readLiteral('*'):
			item = ZeroOrMore(item)
		elif self.readLiteral('+'):
			item = OneOrMore(item)
		return item
	def readClass(self) -> Terminal:
		if not self.readLiteral('['):
			return None
		items = []
		if item := self.readLiteral('^', False):
			items.append(item)
		if item := self.readLiteral('-', False):
			items.append(item)
		while item := self.readClassItem():
			items.append(item)
		if len(items) == 0:
			raise ValueError(self.error("error at %p: expecting char-class items"))
		if self.readLiteral('-', False):
			items.append('-')
			if item := self.readClass():
				items.append(item.text)
		if not self.readLiteral(']', False):
			raise ValueError(self.error("error at %p: expecting closing ']'"))
		return Terminal(f'[{"".join(items)}]', cls="char-class")
	def readClassItem(self) -> str:
		if match := self.readMatch(_class_builtin, False):
			return match.group(0)
		elif match := self.readMatch(_class_item, False):
			return match.group(0)
	def readLiteral(self, value: str, skipWhitespace: bool = True) -> typing.Optional[str]:
		if skipWhitespace:
			self.skipWhitespace()
		if value == self.source[self.off : self.off+len(value)]:
			self.off += len(value)
			return value
	def readMatch(self, regex: re.Pattern, skipWhitespace: bool = True) -> typing.Optional[re.Match]:
		if skipWhitespace:
			self.skipWhitespace()
		if match := regex.match(self.source, self.off):
			self.off = match.end()
			return match
	def skipWhitespace(self) -> None:
		if match := _whitespace.match(self.source, self.off):
			self.off = match.end()
	def error(self, msg: str) -> str:
		msg = str(msg)
		line = 1
		col = 1
		lineStart = 0
		last = None
		for i in range(self.off):
			c = self.source[i]
			if c == '\r':
				line += 1
				col = 1
				lineStart = i
			elif c == '\n':
				if last != '\r':
					line += 1
					col = 1
					lineStart = i
			else:
				col += 1
			last = c
		text_start = max(self.off - 40, lineStart)
		lineEnd = None
		for i in range(self.off, min(self.off + 40, len(self.source))):
			c = self.source[i]
			if c == '\r' or c == '\n':
				lineEnd = i
				break
		text_end = lineEnd or (self.off + 40)
		text = self.source[text_start:text_end]
		offset = self.off - text_start
		msg = msg.replace('%p', f'{line}:{col}')
		cursor = (' ' * offset) + '^'
		return f"{msg}\n{text}\n{cursor}"

