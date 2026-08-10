import duckdb

# Load parquet into the default global database
duckdb.execute("CREATE TABLE test_table AS SELECT 1 as id")

# Try to query it using duckdb.execute directly
print("Query direct:", duckdb.execute("SELECT * FROM test_table").fetchall())

# Try to query it using duckdb.connect() (this should be a separate connection)
try:
    con = duckdb.connect()
    print("Query from connect:", con.execute("SELECT * FROM test_table").fetchall())
except Exception as e:
    print("Error from connect:", e)
