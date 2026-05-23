from neo4j import GraphDatabase
from app.config import settings

class Neo4jClient:
    # Class-level variable to store a single shared Neo4j driver instance
    _driver = None

    @classmethod
    def get_driver(cls):
        """
        Returns an active Neo4j driver instance.
        Creates the driver only once (singleton pattern) and reuses it.
        """
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password)
            )
        return cls._driver

    @classmethod
    def close(cls):
        """
        Closes the Neo4j driver connection if it exists
        and resets the driver instance.
        """
        if cls._driver:
            cls._driver.close()
            cls._driver = None

    @classmethod
    def run_query(cls, cypher: str, parameters: dict = None):
        """
        Executes a Cypher query and returns results as a list of dictionaries.

        Args:
            cypher (str): The Cypher query string.
            parameters (dict, optional): Query parameters.

        Returns:
            list: Query results where each record is converted to a dictionary.
        """
        driver = cls.get_driver()
        with driver.session() as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]