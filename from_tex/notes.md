Convert full doc to markdown:

`pandoc techreport.tex -o test.md`

Split markdown file by headings:

`awk -F, '/^# /{h=substr($0,3);} {print > ( h ".md")}' test.md`
