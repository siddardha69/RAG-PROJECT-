import re
from typing import List, Set
import spacy
from pydantic import BaseModel
from app.services.chunking.chunking_engine import Chunk


class ExtractedEntities(BaseModel):
    """Data class containing all entities parsed from text."""

    technologies: List[str]
    services: List[str]
    file_paths: List[str]
    issue_refs: List[str]
    pr_refs: List[str]
    people: List[str]


class EntityExtractor:
    """Hybrid entity extractor utilizing spaCy and regex-based rulers."""

    def __init__(self) -> None:
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Fallback if model isn't downloaded yet
            spacy.cli.download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

        # Define technologies to match explicitly
        self.common_techs = {
            "Redis",
            "Postgres",
            "PostgreSQL",
            "MySQL",
            "MongoDB",
            "Kafka",
            "RabbitMQ",
            "JWT",
            "OAuth",
            "Docker",
            "Kubernetes",
            "React",
            "FastAPI",
            "Django",
            "Flask",
            "Express",
            "Next.js",
            "GraphQL",
            "REST",
            "gRPC",
            "S3",
            "Lambda",
            "SQLite",
            "Celery",
            "Neo4j",
            "Qdrant",
            "Git",
            "GitHub",
            "Vite",
            "TypeScript",
            "Python",
            "Java",
            "Go",
            "Rust",
            "C++",
            "Javascript",
            "CSS",
            "Tailwind",
            "SQLAlchemy",
            "Alembic",
        }

        # Add entity ruler for Technologies
        ruler = self.nlp.add_pipe("entity_ruler", before="ner")
        patterns = []
        for tech in self.common_techs:
            patterns.append(
                {
                    "label": "TECHNOLOGY",
                    "pattern": [{"LOWER": tech.lower()}],
                    "id": tech,
                }
            )
        ruler.add_patterns(patterns)

        # Precompile Regexes
        self.issue_ref_pattern = re.compile(
            r"#(\d+)|issues?\s*#?(\d+)",
            re.IGNORECASE,
        )
        self.pr_ref_pattern = re.compile(
            r"PR\s*#?(\d+)|pull\s+request\s*#?(\d+)|pulls?\s*#?(\d+)|pull/(\d+)",
            re.IGNORECASE,
        )
        self.file_path_pattern = re.compile(
            r"\b[\w\-./]+\.(?:py|js|ts|tsx|json|yml|yaml|md|ini|sh|sql|dockerfile|conf)\b",
            re.IGNORECASE,
        )
        self.service_name_pattern = re.compile(
            r"\b\w+[-_](?:service|worker|job|handler|client|api)\b",
            re.IGNORECASE,
        )

    def extract(self, text: str) -> ExtractedEntities:
        """Extract entities from raw text using custom regex and spaCy NER."""
        doc = self.nlp(text)

        technologies: Set[str] = set()
        people: Set[str] = set()

        for ent in doc.ents:
            if ent.label_ == "TECHNOLOGY":
                # Match normalized technology name from pattern id
                # Or fall back to entity text title-cased
                tech_name = ent.ent_id_ or ent.text
                # Find matching tech from our dictionary to keep capitalization consistent
                matched = next(
                    (t for t in self.common_techs if t.lower() == tech_name.lower()),
                    tech_name,
                )
                technologies.add(matched)
            elif ent.label_ == "PERSON":
                # Filter out obvious false positives (like tech terms)
                name = ent.text.strip()
                if (
                    len(name) > 2
                    and name.lower() not in [t.lower() for t in self.common_techs]
                    and not any(char.isdigit() for char in name)
                ):
                    people.add(name)

        # Regex Extracts
        issue_refs = []
        for match in self.issue_ref_pattern.finditer(text):
            num = match.group(1) or match.group(2)
            if num:
                issue_refs.append(f"#{num}")

        pr_refs = []
        for match in self.pr_ref_pattern.finditer(text):
            num = (
                match.group(1)
                or match.group(2)
                or match.group(3)
                or match.group(4)
            )
            if num:
                pr_refs.append(f"PR #{num}")

        file_paths = [match.group(0) for match in self.file_path_pattern.finditer(text)]
        services = [match.group(0) for match in self.service_name_pattern.finditer(text)]

        # Let's also do a quick substring match for techs that might have been missed by NER
        lower_text = text.lower()
        for tech in self.common_techs:
            # check for word boundaries
            if re.search(r"\b" + re.escape(tech.lower()) + r"\b", lower_text):
                technologies.add(tech)

        return ExtractedEntities(
            technologies=sorted(list(technologies)),
            services=sorted(list(set(services))),
            file_paths=sorted(list(set(file_paths))),
            issue_refs=sorted(list(set(issue_refs))),
            pr_refs=sorted(list(set(pr_refs))),
            people=sorted(list(people)),
        )

    def extract_from_chunk(self, chunk: Chunk) -> ExtractedEntities:
        """Extract entities directly from a Chunk object."""
        entities = self.extract(chunk.text)
        if chunk.author and chunk.author != "system" and chunk.author != "unknown":
            if chunk.author not in entities.people:
                entities.people.append(chunk.author)
        return entities
