from abc import ABC, abstractmethod
import re

import railroad as rr

# Syntax ABC
class Node(ABC):
	@abstractmethod
	def toEbnf(self, group): pass
	@abstractmethod
	def toRailroad(self): pass
	@abstractmethod
	def __len__(self): pass
class Container(Node):
	def __init__(self, items, sep):
		if len(items) <= 0:
			raise ValueError("need at least one item")
		self.items = items
		self.sep = str(sep)
	def toEbnf(self, group=False):
		if len(self.items) > 1:
			text = self.sep.join(x.toEbnf(True) for x in self.items)
			return f'({text})' if group else text
		else:
			return self.items[0].toEbnf(group)
	def itemsAsRailroad(self):
		return (x.toRailroad() for x in self.items)
	def __len__(self):
		return len(self.items)
class Quantifier(Node):
	def __init__(self, item: Node, suffix: str):
		self.item = item
		self.suffix = suffix
	def toEbnf(self, group=False) -> str:
		return self.item.toEbnf(True) + self.suffix
	def __len__(self) -> int:
		return 1
class Leaf(Node):
	def __len__(self) -> int:
		return 1

# render
def renderEbnf(item, write, prefix:str='', sep:str='\n'):
	if isinstance(item, str):
		item = Reader(item).read()
	if isinstance(item, Alternation):
		write(f'{prefix}::= {item.items[0].toEbnf()}')
		for i in range(1, len(item.items)):
			write(f'{sep}{prefix}  | {item.items[i].toEbnf()}')
	else:
		write(f'{prefix}::= {item.toEbnf()}')
def renderRailroad(item, write, css=rr.DEFAULT_STYLE):
	if isinstance(item, str):
		item = Reader(item).read()
	rr.Diagram(item.toRailroad(), css=css).writeSvg(write)

# Containers
class Alternation(Container):
	def __init__(self, *items):
		super().__init__(items, ' | ')
	def toRailroad(self):
		return rr.Choice(0, *self.itemsAsRailroad())
class Sequence(Container):
	def __init__(self, *items):
		super().__init__(items, ' ')
	def toRailroad(self):
		return rr.Sequence(*self.itemsAsRailroad())

# Quantifiers
class Optional(Quantifier):
	def __init__(self, item: Node):
		super().__init__(item, '?')
	def toRailroad(self):
		return rr.Optional(self.item.toRailroad())
class ZeroOrMore(Quantifier):
	def __init__(self, item: Node):
		super().__init__(item, '*')
	def toRailroad(self):
		return rr.ZeroOrMore(self.item.toRailroad())
class OneOrMore(Quantifier):
	def __init__(self, item: Node):
		super().__init__(item, '+')
	def toRailroad(self):
		return rr.OneOrMore(self.item.toRailroad())

# Leaf
class Terminal(Leaf):
	def __init__(self, text, cls = ''):
		self.text = text
	def toEbnf(self, group=False):
		return self.text
	def toRailroad(self):
		return rr.Terminal(self.text)
class NonTerminal(Leaf):
	def __init__(self, text):
		self.text = text
	def toEbnf(self, group=False):
		return self.text
	def toRailroad(self):
		return rr.NonTerminal(self.text)

class Reader:
	def __init__(self, source):
		self.source = str(source)
		self.off = 0
	def read(self):
		alternation = self.readAlternation()
		if self.off < len(self.source):
			raise ValueError(self.error("error at %p: invalid character"))
		return alternation
	def readAlternation(self):
		alternation = []
		while True:
			alternation.append(self.readSequence())
			if not self.readLiteral('|'):
				break
		if len(alternation) > 1:
			return Alternation(*alternation)
		else:
			return alternation[0]
	def readSequence(self):
		sequence = []
		while True:
			if item := self.readItem():
				sequence.append(item)
			else:
				break
		return Sequence(*sequence)
	def readItem(self):
		if match := self.readMatch(r"\w[\w.-]*"):
			# identifier
			item = NonTerminal(match.group(0))
		elif match := self.readMatch(r"\'(?:[^\'\\]|\\.)*\'"):
			# literal
			item = Terminal(match.group(0), cls="literal")
		elif match := self.readMatch(r'/(?:[^/\\]|\\.)*/i?'):
			# regex
			item = Terminal(match.group(0), cls="regex")
		elif item := self.readClass():
			pass
		elif self.readLiteral('.'):
			item = Terminal('.', cls="char-class")
		elif self.readLiteral('('):
			item = self.readAlternation()
			if not item:
				raise ValueError(self.error("error at %p: expecting alternation after '('"))
			if not self.readLiteral(')'):
				raise ValueError(self.error("error at %p: expecting closing brace ')'"))
		else:
			return None
		if self.readLiteral('?'):
			item = Optional(item)
		elif self.readLiteral('*'):
			item = ZeroOrMore(item)
		elif self.readLiteral('+'):
			item = OneOrMore(item)
		return item
	def readClass(self):
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
				items.append(item)
		if not self.readLiteral(']', False):
			raise ValueError(self.error("error at %p: expecting closing ']'"))
		return Terminal(f'[{"".join(items)}]', cls="char-class")
	def readClassItem(self):
		c = r'(?:[^\[\]\\-]|\\[\[\]\\-]|\\x[\da-fA-F]{2})'
		if match := self.readMatch(r'\\[DSWdsw]', False):
			return match.group(0)
		elif match := self.readMatch(rf'{c}(?:-(?:{c}))?', False):
			return match.group(0)
	def readLiteral(self, value, skipWhitespace = True):
		if skipWhitespace:
			self.skipWhitespace()
		if value == self.source[self.off : self.off+len(value)]:
			self.off += len(value)
			return value
	def readMatch(self, regex, skipWhitespace = True):
		if skipWhitespace:
			self.skipWhitespace()
		if match := re.compile(regex).match(self.source, self.off):
			self.off = match.end()
			return match
	def skipWhitespace(self):
		if match := re.compile(r'\s+').match(self.source, self.off):
			self.off = match.end()
	def error(self, msg):
		msg = str(msg)
		source = self.source
		line = 1
		col = 1
		last = None
		for i in range(self.off):
			c = source[i]
			if c == '\r':
				line += 1
				col = 1
			elif c == '\n':
				if last != '\r':
					line += 1
					col = 1
			else:
				col += 1
			last = c
		return msg.replace('%p', f"{line}:{col}")

