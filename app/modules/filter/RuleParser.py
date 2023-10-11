from pyparsing import Forward, Literal, Word, alphas, infixNotation, opAssoc, alphanums, Combine, nums, ParseResults


class RuleParser:

    def __init__(self):
        """
        Defining grammar rules
        """
        #  Displayed formula
        expr: Forward = Forward()
        #  Atomic
        atom: Combine = Combine(Word(alphas, alphanums) | Word(nums) + Word(alphas, alphanums))
        #  Logical nonoperator
        operator_not: Literal = Literal('!').setParseAction(lambda: 'not')
        #  Logical or operator (math.)
        operator_or: Literal = Literal('|').setParseAction(lambda: 'or')
        #  Logic and operators (math.)
        operator_and: Literal = Literal('&').setParseAction(lambda: 'and')
        #  Syntax rules for defining expressions
        expr <<= operator_not + expr | operator_or | operator_and | atom | ('(' + expr + ')')

        #  Operator priority
        self.expr = infixNotation(expr,
                                  [(operator_not, 1, opAssoc.RIGHT),
                                   (operator_and, 2, opAssoc.LEFT),
                                   (operator_or, 2, opAssoc.LEFT)])

    def parse(self, expression: str) -> ParseResults:
        """
        Parses the given expression。

        Parameters:
        expression --  The expression to be parsed

        Come (or go) back:
        Parsing result
        """
        return self.expr.parseString(expression)


if __name__ == '__main__':
    #  Test code
    expression_str = "!BLU & 4K & CN > !BLU & 1080P & CN > !BLU & 4K > !BLU & 1080P"
    for exp in expression_str.split('>'):
        parsed_expr = RuleParser().parse(exp)
        print(parsed_expr.as_list())
