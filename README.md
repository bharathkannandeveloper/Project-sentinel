# Project Sentinel

**Autonomous Financial Analyst System** powered by Multi-LLM Providers and GraphRAG

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Django 6.0](https://img.shields.io/badge/django-6.0-green.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Project Sentinel is an autonomous financial analysis system implementing the **Pattaasu** investment methodology. It leverages:

- **Multi-LLM Support**: Groq (default), Ollama, OpenAI, Anthropic Claude, Google Gemini, xAI Grok, Together AI, OpenRouter
- **GraphRAG**: Neo4j-based knowledge graph with FIBO ontology
- **Distributed Processing**: Celery with Canvas patterns for scalable data ingestion
- **Real-time Dashboard**: Django Channels with WebSocket streaming

## Pattaasu Investment Criteria

1. **Zero/Low Debt**: Debt-to-Equity ratio < 1.0
2. **No Promoter Pledging**: 0% shares pledged
3. **Positive Cash Flow**: FCF positive for 3 consecutive years
4. **Strong Moat**: Demonstrated pricing power

## Quick Start

### Prerequisites

- Python 3.12+
- Redis (for Celery)
- Neo4j 5+ (for Knowledge Graph)
- Docker (optional, for services)

### Installation

```bash
# Clone the repository
cd STOCK

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .

# Copy environment file
copy .env.example .env
# Edit .env with your API keys
```

### Start Services (Docker)

```bash
# Start Redis and Neo4j
docker compose -f docker/docker-compose.yml up -d
```

### Run the Application

```bash
# Apply migrations
python manage.py migrate

# Start development server
python manage.py runserver

# In another terminal - start Celery worker
celery -A sentinel_core worker -l INFO
```

Access the dashboard at: http://localhost:8000

## Configuration

### LLM Providers

Edit `.env` to configure API keys:

```env
# Default provider (Groq)
GROQ_API_KEY=your_groq_key

# Local LLMs (no key needed)
OLLAMA_BASE_URL=http://localhost:11434

# Optional providers
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_gemini_key
```

### Provider Priority

1. **Groq** - Default, high-speed inference
2. **Ollama** - Local fallback
3. Other providers as configured

## API Endpoints

| Endpoint                          | Method | Description                |
| --------------------------------- | ------ | -------------------------- |
| `/`                               | GET    | Dashboard home             |
| `/api/analysis/validate/`         | POST   | Validate Pattaasu criteria |
| `/api/analysis/analyze/<ticker>/` | GET    | Full stock analysis        |
| `/api/ingestion/fetch/<ticker>/`  | POST   | Fetch company data         |
| `/api/ingestion/sector/<sector>/` | POST   | Analyze sector             |
| `/api/providers/`                 | GET    | LLM provider status        |

## WebSocket Endpoints

- `ws://localhost:8000/ws/market/` - Real-time market data
- `ws://localhost:8000/ws/analysis/` - Analysis progress

## Architecture

```
sentinel_core/          # Django project
├── settings/           # Environment-specific settings
├── celery.py          # Celery configuration
└── asgi.py            # ASGI with Channels

src/
├── llm/               # Multi-LLM provider module
│   ├── providers/     # Provider implementations
│   ├── manager.py     # Provider orchestration
│   └── tokenizer.py   # Token management
├── analysis/          # Pattaasu analysis
│   ├── models.py      # Pydantic validation
│   └── pattaasu.py    # Analysis engine
├── ingestion/         # Data ingestion
│   ├── tasks.py       # Celery tasks
│   └── handlers.py    # Error handling
├── knowledge/         # GraphRAG
│   └── ontology.py    # FIBO ontology
└── dashboard/         # Web interface
    ├── consumers.py   # WebSocket consumers
    └── views.py       # Async views
```

## Development

```bash
# Run tests
pytest

# Lint code
ruff check .

# Type checking
mypy src/
```

## License

MIT License - See LICENSE file for details.
