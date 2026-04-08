from neo4j import GraphDatabase
from app.config import settings

class Neo4jClient:
    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password)
            )
        return cls._driver

    @classmethod
    def close(cls):
        if cls._driver:
            cls._driver.close()
            cls._driver = None

    @classmethod
    def run_query(cls, cypher: str, parameters: dict = None):
        driver = cls.get_driver()
        with driver.session() as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]