"""PubMed/MEDLINE literature search tools — article search, clinical queries, abstracts.
Migrated from standalone pubmed MCP server."""

import logging
import os
from typing import Optional
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")  # Optional but recommended

# NCBI E-utilities endpoints
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

TOOLS = [
    {
        "name": "search_pubmed",
        "description": "Search PubMed for medical literature. Returns article IDs and basic metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (supports PubMed search syntax, MeSH terms, boolean operators)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (1-100, default 20)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                },
                "sort": {
                    "type": "string",
                    "enum": ["relevance", "pub_date", "first_author"],
                    "description": "Sort order for results",
                    "default": "relevance",
                },
                "date_range": {
                    "type": "object",
                    "properties": {"from_year": {"type": "integer"}, "to_year": {"type": "integer"}},
                    "description": "Filter by publication date range",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_article",
        "description": "Get detailed information about a specific PubMed article by PMID.",
        "inputSchema": {
            "type": "object",
            "properties": {"pmid": {"type": "string", "description": "PubMed ID (PMID) of the article"}},
            "required": ["pmid"],
        },
    },
    {
        "name": "get_articles_batch",
        "description": "Get details for multiple PubMed articles by PMIDs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pmids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of PubMed IDs",
                    "maxItems": 50,
                }
            },
            "required": ["pmids"],
        },
    },
    {
        "name": "get_article_abstract",
        "description": "Get the abstract text for a PubMed article.",
        "inputSchema": {
            "type": "object",
            "properties": {"pmid": {"type": "string", "description": "PubMed ID"}},
            "required": ["pmid"],
        },
    },
    {
        "name": "find_related_articles",
        "description": "Find articles related to a specific PubMed article.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pmid": {"type": "string", "description": "PubMed ID of the reference article"},
                "max_results": {"type": "integer", "default": 10, "maximum": 50},
            },
            "required": ["pmid"],
        },
    },
    {
        "name": "search_clinical_queries",
        "description": "Search PubMed using clinical study category filters (therapy, diagnosis, prognosis, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "category": {
                    "type": "string",
                    "enum": ["therapy", "diagnosis", "prognosis", "etiology", "clinical_prediction_guides"],
                    "description": "Clinical study category filter",
                },
                "scope": {
                    "type": "string",
                    "enum": ["broad", "narrow"],
                    "description": "Search scope - broad is more sensitive, narrow is more specific",
                    "default": "narrow",
                },
                "max_results": {"type": "integer", "default": 20, "maximum": 100},
            },
            "required": ["query", "category"],
        },
    },
]

# Clinical query filters (PubMed clinical queries)
CLINICAL_FILTERS = {
    "therapy": {
        "narrow": "((clinical[Title/Abstract] AND trial[Title/Abstract]) OR clinical trials as topic[MeSH Terms] OR clinical trial[Publication Type] OR random*[Title/Abstract] OR random allocation[MeSH Terms] OR therapeutic use[MeSH Subheading])",
        "broad": "(clinical trial[Publication Type] OR (clinical[Title/Abstract] AND trial[Title/Abstract]) OR clinical trials as topic[MeSH Terms] OR random*[Title/Abstract] OR control*[Title/Abstract])",
    },
    "diagnosis": {
        "narrow": "(sensitivity and specificity[MeSH Terms] OR (predictive[Title/Abstract] AND value*[Title/Abstract]) OR accuracy[Title/Abstract])",
        "broad": "(sensitivity and specificity[MeSH Terms] OR diagnosis[MeSH Subheading] OR diagnostic[Title/Abstract])",
    },
    "prognosis": {
        "narrow": "(prognosis[MeSH Terms] OR (disease[Title/Abstract] AND progression[Title/Abstract]) OR mortality[MeSH Terms])",
        "broad": "(prognosis[MeSH Terms] OR survival[Title/Abstract] OR outcome[Title/Abstract])",
    },
    "etiology": {
        "narrow": "(risk[MeSH Terms] OR (odds[Title/Abstract] AND ratio*[Title/Abstract]) OR (relative[Title/Abstract] AND risk[Title/Abstract]))",
        "broad": "(risk[MeSH Terms] OR etiology[MeSH Subheading] OR caus*[Title/Abstract])",
    },
    "clinical_prediction_guides": {
        "narrow": "(predict*[Title/Abstract] AND (valid*[Title/Abstract] OR rule*[Title/Abstract]))",
        "broad": "(predict*[Title/Abstract] OR score[Title/Abstract] OR model[Title/Abstract])",
    },
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_base_params() -> dict:
    """Get base parameters for NCBI API calls."""
    params = {"tool": "healthcare-mcp-server", "email": "mcp@healthcare.azure"}
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    return params


async def _get_summaries(pmids: list[str]) -> list[dict]:
    """Get article summaries for PMIDs."""
    params = {**_get_base_params(), "db": "pubmed", "id": ",".join(pmids), "retmode": "json"}

    async with httpx.AsyncClient() as client:
        response = await client.get(ESUMMARY_URL, params=params)
        response.raise_for_status()
        data = response.json()

        articles = []
        result = data.get("result", {})

        for pmid in pmids:
            if pmid in result:
                article = result[pmid]
                articles.append(
                    {
                        "pmid": pmid,
                        "title": article.get("title", ""),
                        "authors": [a.get("name", "") for a in article.get("authors", [])[:5]],
                        "journal": article.get("fulljournalname", ""),
                        "pub_date": article.get("pubdate", ""),
                        "doi": next(
                            (i.get("value") for i in article.get("articleids", []) if i.get("idtype") == "doi"), None
                        ),
                        "pub_type": article.get("pubtype", []),
                    }
                )

        return articles


def _parse_article_xml(xml_text: str, pmid: str) -> dict:
    """Parse PubMed article XML."""
    try:
        root = ET.fromstring(xml_text)
        article = root.find(".//PubmedArticle")

        if not article:
            return {"pmid": pmid, "found": False}

        medline = article.find(".//MedlineCitation")
        article_elem = medline.find(".//Article")

        # Title
        title_elem = article_elem.find(".//ArticleTitle")
        title = "".join(title_elem.itertext()) if title_elem is not None else ""

        # Abstract
        abstract_elem = article_elem.find(".//Abstract")
        abstract_parts = []
        if abstract_elem is not None:
            for text in abstract_elem.findall(".//AbstractText"):
                label = text.get("Label", "")
                content = "".join(text.itertext())
                if label:
                    abstract_parts.append(f"{label}: {content}")
                else:
                    abstract_parts.append(content)
        abstract = "\n\n".join(abstract_parts)

        # Authors
        authors = []
        for author in article_elem.findall(".//Author"):
            last = author.findtext("LastName", "")
            first = author.findtext("ForeName", "")
            if last:
                authors.append(f"{last} {first}".strip())

        # Journal
        journal = article_elem.findtext(".//Journal/Title", "")

        # Publication date
        pub_date_elem = article_elem.find(".//Journal/JournalIssue/PubDate")
        pub_date = ""
        if pub_date_elem is not None:
            year = pub_date_elem.findtext("Year", "")
            month = pub_date_elem.findtext("Month", "")
            pub_date = f"{year} {month}".strip()

        # MeSH terms
        mesh_terms = []
        for mesh in medline.findall(".//MeshHeading/DescriptorName"):
            mesh_terms.append(mesh.text)

        # Keywords
        keywords = []
        for kw in medline.findall(".//KeywordList/Keyword"):
            keywords.append(kw.text)

        return {
            "pmid": pmid,
            "found": True,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "journal": journal,
            "pub_date": pub_date,
            "mesh_terms": mesh_terms[:15],
            "keywords": keywords[:10],
        }
    except Exception as e:
        logger.exception(f"Error parsing XML for PMID {pmid}")
        return {"pmid": pmid, "found": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tool implementation functions
# ---------------------------------------------------------------------------


async def search_pubmed(
    query: str, max_results: int = 20, sort: str = "relevance", date_range: Optional[dict] = None
) -> dict:
    """Search PubMed for articles."""
    params = {
        **_get_base_params(),
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": sort,
    }

    if date_range:
        if date_range.get("from_year"):
            params["mindate"] = f"{date_range['from_year']}/01/01"
        if date_range.get("to_year"):
            params["maxdate"] = f"{date_range['to_year']}/12/31"
        params["datetype"] = "pdat"

    async with httpx.AsyncClient() as client:
        response = await client.get(ESEARCH_URL, params=params)
        response.raise_for_status()
        data = response.json()

        result = data.get("esearchresult", {})
        pmids = result.get("idlist", [])

        # Get summaries for found articles
        articles = []
        if pmids:
            articles = await _get_summaries(pmids)

        return {
            "query": query,
            "total_count": int(result.get("count", 0)),
            "returned_count": len(pmids),
            "articles": articles,
        }


async def get_article(pmid: str) -> dict:
    """Get detailed article information."""
    params = {**_get_base_params(), "db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "xml"}

    async with httpx.AsyncClient() as client:
        response = await client.get(EFETCH_URL, params=params)
        response.raise_for_status()

        return _parse_article_xml(response.text, pmid)


async def get_articles_batch(pmids: list[str]) -> dict:
    """Get multiple articles."""
    articles = await _get_summaries(pmids)
    return {"requested": len(pmids), "returned": len(articles), "articles": articles}


async def get_article_abstract(pmid: str) -> dict:
    """Get article abstract."""
    article = await get_article(pmid)
    return {
        "pmid": pmid,
        "title": article.get("title", ""),
        "abstract": article.get("abstract", "No abstract available"),
    }


async def find_related_articles(pmid: str, max_results: int = 10) -> dict:
    """Find related articles using PubMed's related articles feature."""
    params = {
        **_get_base_params(),
        "db": "pubmed",
        "dbfrom": "pubmed",
        "cmd": "neighbor_score",
        "id": pmid,
        "retmode": "json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi", params=params)
        response.raise_for_status()
        data = response.json()

        # Extract related PMIDs
        related_pmids = []
        linksets = data.get("linksets", [])
        if linksets and linksets[0].get("linksetdbs"):
            for linkdb in linksets[0]["linksetdbs"]:
                if linkdb.get("linkname") == "pubmed_pubmed":
                    related_pmids = [str(link.get("id")) for link in linkdb.get("links", [])][:max_results]

        articles = []
        if related_pmids:
            articles = await _get_summaries(related_pmids)

        return {"reference_pmid": pmid, "related_count": len(articles), "articles": articles}


async def search_clinical_queries(query: str, category: str, scope: str = "narrow", max_results: int = 20) -> dict:
    """Search using clinical query filters."""
    filter_query = CLINICAL_FILTERS.get(category, {}).get(scope, "")

    full_query = f"({query}) AND {filter_query}" if filter_query else query

    result = await search_pubmed(full_query, max_results)
    result["category"] = category
    result["scope"] = scope
    result["original_query"] = query

    return result


# ---------------------------------------------------------------------------
# Handler dispatch map
# ---------------------------------------------------------------------------

HANDLERS = {
    "search_pubmed": lambda args: search_pubmed(
        args.get("query", ""), args.get("max_results", 20),
        args.get("sort", "relevance"), args.get("date_range"),
    ),
    "get_article": lambda args: get_article(args.get("pmid", "")),
    "get_articles_batch": lambda args: get_articles_batch(args.get("pmids", [])),
    "get_article_abstract": lambda args: get_article_abstract(args.get("pmid", "")),
    "find_related_articles": lambda args: find_related_articles(
        args.get("pmid", ""), args.get("max_results", 10)
    ),
    "search_clinical_queries": lambda args: search_clinical_queries(
        args.get("query", ""), args.get("category", "therapy"),
        args.get("scope", "narrow"), args.get("max_results", 20),
    ),
}
