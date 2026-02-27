import sqlite3
c1 = sqlite3.connect('F:/BUREAU/turbo/data/etoile.db')
c2 = sqlite3.connect('F:/BUREAU/turbo/data/jarvis.db')
p = c1.execute('SELECT COUNT(*) FROM pipeline_dictionary').fetchone()[0]
d = c1.execute('SELECT COUNT(*) FROM domino_chains').fetchone()[0]
w = c1.execute('SELECT COUNT(*) FROM scenario_weights').fetchone()[0]
s = c2.execute('SELECT COUNT(*) FROM scenarios').fetchone()[0]
sh = c2.execute("SELECT COUNT(*) FROM scenarios WHERE difficulty='hard'").fetchone()[0]
print(f'P:{p} D:{d} S:{s}({sh}h) W:{w} = {p+d+s+w}')
