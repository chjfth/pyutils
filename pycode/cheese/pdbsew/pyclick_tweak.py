"""This module provides a workaround for Click 8.1.3 HelpFormatter.writedl()'s
hardcoding of parameter default value col_max=30, and I want it to be a smaller
value like col_max=5 .

Thanks to: https://stackoverflow.com/a/73415910/151453
"""

import click

class MyHelpFormatter(click.HelpFormatter):
	def write_dl(self, rows, col_max=5, col_spacing=2):
		super().write_dl(rows, col_max, col_spacing)

click.Context.formatter_class = MyHelpFormatter
