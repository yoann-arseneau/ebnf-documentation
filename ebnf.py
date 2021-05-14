import re

# Containers
class Alternation:
	def __init__(self, *items):
		if len(items) < 2:
			raise ValueError("must have at least two item")
		self.items = items
class Sequence:
	def __init__(self, *items):
		if len(items) < 2:
			raise ValueError("must have at least two item")
		self.items = items

# Quantifiers
class Optional:
	def __init__(self, item):
		self.item = item
class ZeroOrMore:
	def __init__(self, item):
		self.item = item
class OneOrMore:
	def __init__(self, item):
		self.item = item

# Leaf
class Terminal:
	def __init__(self, text, cls = None):
		self.text = text
		self.cls = cls or ''
class NonTerminal:
	def __init__(self, text):
		self.text = text

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
		elif len(alternation) == 1:
			return alternation[0]
		else:
			raise ValueError(self.error("error at %p: unexpected end of text"))
	def readSequence(self):
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
			raise ValueError(self.error("error at %p: unexpected end of text"))
	def readItem(self):
		# read item
		if match := self.readMatch(r"\w[\w.-]*"):
			# identifier
			item = NonTerminal(match.group(0))
		elif match := self.readMatch(r"\'(?:[^\'\\]|\\.)*\'"):
			# literal
			item = Terminal(match.group(0), cls="literal")
		elif match := self.readMatch(r'/\*[^*]*(?:[^/][^*]*)*\*/'):
			# comment
			return Terminal(match.group(0), cls="comment")
		elif match := self.readMatch(r'/(?:[^/\\]|\\.)*/i?'):
			# regex
			return Terminal(match.group(0), cls="regex")
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

