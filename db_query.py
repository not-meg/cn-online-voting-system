import pprint
import sqlite3

conn = sqlite3.connect('poll_database.sqldb')
pprint.pprint(conn.execute("select * from sqlite_schema where name = 'user_table'").fetchall())
pprint.pprint(conn.execute("select * from sqlite_schema where name = 'poll_master_table'").fetchall())
pprint.pprint(conn.execute("select * from sqlite_schema where name = 'poll_choices_table'").fetchall())
pprint.pprint(conn.execute("select * from sqlite_schema where name = 'user_poll_selection_table'").fetchall())

print('user_table : ')
pprint.pprint(conn.execute('select * from user_table').fetchall())

print('poll_master_table : ')
pprint.pprint(conn.execute('select * from poll_master_table').fetchall())

print('poll_choices_table : ')
pprint.pprint(conn.execute('select * from poll_choices_table').fetchall())

print('user_poll_selection_table : ')
pprint.pprint(conn.execute('select * from user_poll_selection_table').fetchall())
