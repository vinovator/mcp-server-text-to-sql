from mcp.server.fastmcp import FastMCP
import duckdb
import os

# Initialize the MCP server
mcp = FastMCP("text-to-sql-mcp-server")

# Get the CSV file path relative to this script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_FILE = os.path.join(BASE_DIR, "data", "AI_Impact_on_Jobs_2030.csv")

# Extract the schema ONCE at server startup
def get_schema_string() -> str:
    """Extracts the schema from the CSV file to inject into the tool description."""
    try:
        query = f"DESCRIBE SELECT * FROM read_csv_auto('{CSV_FILE}')"
        with duckdb.connect() as con:
            return con.execute(query).df().to_csv(index=False)
    except Exception as e:
        return f"Schema extraction failed: {str(e)}"

SCHEMA_TEXT = get_schema_string()

# Define Resources
@mcp.resource("resource://database/schema")
def get_database_schema() -> str:
    """
    Returns the schema of the DuckDB database.
    """
    return SCHEMA_TEXT


@mcp.resource("resource://business/glossary")
def get_business_glossary() -> str:
    """
    Provides the business context for the data.
    """
    return f"""
    # AI Jobs 2030 Database Glossary
    - The main table can be queried using: read_csv_auto('{CSV_FILE}')
    - `Required_Skills`: Contains comma-separated skills. Use SQL LIKE '%Skill%' to search.
    - `Remote_Work_Possibility` & `Upskilling_Needed`: Values are strictly 'Yes' or 'No'.
    - `Job_Growth_2030`: An integer representing projected growth. Negative numbers mean the job is shrinking.
    - `Average_Salary_USD`: Stored as plain integers.
    """

#------------------------

# Build the tool description dynamically with the extracted schema
TOOL_DESCRIPTION = f"""
Executes a read-only SQL query against the AI Impact on Jobs 2030 dataset using DuckDB.

CRITICAL BUSINESS RULES FOR WRITING SQL:
1. Table Name: You MUST query `read_csv_auto('{CSV_FILE}')`.
2. Missing Values: 'Remote_Work_Possibility' and 'Upskilling_Needed' values are strictly 'Yes' or 'No'.
3. Arrays: 'Required_Skills' contains comma-separated text. Use LIKE '%Skill%' instead of exact matches.
4. Data Types: 'Average_Salary_USD' and 'Job_Growth_2030' are plain integers.
5. Metric Scales: 'Job_Growth_2030' can be negative (indicating decline).

DATABASE SCHEMA:
{SCHEMA_TEXT}
"""

# Define the tools
@mcp.tool(description=TOOL_DESCRIPTION)
def execute_analytical_query(sql_query: str) -> str:
    """Executes a read-only SQL query against the dataset."""

    # Basic validation for read-only query
    if not sql_query.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are allowed for read-only analytical execution."

    try:
        with duckdb.connect() as con:
            result_df = con.execute(sql_query).df()

            if result_df.empty:
                return "Query executed. But returned no results."  

            return result_df.to_json(orient="records", indent=2)

    except duckdb.Error as e:
        return f"SQL Execution Error. Please fix the SQL and try again. Error details: {str(e)}"

if __name__ == "__main__":
    mcp.run()