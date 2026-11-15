# Technology Stack & Rationale - ReSearch Flow

## Overview

ReSearch Flow is built using modern web technologies with a focus on performance, scalability, and developer experience. This document explains **why** each technology was chosen and **how** it fits into the overall system.

---

## Frontend Technologies

### Core Framework

#### ⚛️ React 19 (with Vite)

**Why React?**
- ✅ Component-based architecture (reusable UI components)
- ✅ Large ecosystem and community support
- ✅ Excellent documentation and learning resources
- ✅ Virtual DOM for efficient updates
- ✅ Hooks API for state management
- ✅ Team familiarity and experience

**Why React 19?**
- Latest version with performance improvements
- Better error handling and debugging
- Enhanced concurrent features
- Improved server components (future-ready)

**Why Vite?**
- ⚡ Lightning-fast HMR (Hot Module Replacement)
- 🚀 Instant server start
- 📦 Optimized production builds
- 🔧 Better developer experience than Create React App
- 🔌 Built-in support for modern features (ES modules)

**Alternatives Considered**:
- Next.js: Overkill for our use case (no SSR needed initially)
- Vue.js: Less familiar to team
- Angular: Too opinionated, steeper learning curve

---

### Styling

#### 🎨 Tailwind CSS 4

**Why Tailwind?**
- ✅ Utility-first approach (rapid development)
- ✅ No CSS file management (styles in JSX)
- ✅ Consistent design system
- ✅ Responsive design utilities
- ✅ Small production bundle (unused styles purged)
- ✅ Excellent documentation

**Example**:
```jsx
// Traditional CSS
<div className="paper-card">
  <h3 className="paper-title">Title</h3>
</div>

// Tailwind CSS
<div className="bg-white rounded-lg border border-gray-300 shadow-lg p-6">
  <h3 className="text-xl font-semibold text-black">Title</h3>
</div>
```

**Alternatives Considered**:
- Bootstrap: Too opinionated, harder to customize
- Material-UI: Heavy bundle size, specific design language
- Styled-components: Requires more boilerplate

---

### Routing

#### 🧭 React Router v7

**Why React Router?**
- ✅ De facto standard for React routing
- ✅ Declarative routing
- ✅ Nested routes and layouts
- ✅ Built-in hooks (useNavigate, useParams, useSearchParams)
- ✅ Code splitting support

**Use Cases**:
- `/` - Home page
- `/results?topic=...` - Search results
- `/saved-searches` - User's saved papers
- `/auth` - Authentication pages
- `/auth/callback` - OAuth redirect

---

### State Management

#### 🔄 React Context API

**Why Context API?**
- ✅ Built into React (no extra dependency)
- ✅ Perfect for global state (auth, theme)
- ✅ Simple API (Provider, useContext)
- ✅ Sufficient for our needs

**Current Contexts**:
- `AuthContext`: User authentication state

**When to use**:
- Global state (user, theme, language)
- Data needed by many components

**When NOT to use**:
- Frequently changing state (performance issues)
- Large, complex state (use Zustand/Redux if needed)

---

### UI Libraries

#### 🎬 Framer Motion

**Why Framer Motion?**
- ✅ Declarative animations
- ✅ Excellent performance
- ✅ Easy to use
- ✅ Spring physics animations

**Use Cases**:
- Page transitions
- Component mount/unmount animations
- Hover effects
- Modal animations

**Example**:
```jsx
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.5 }}
>
  Content
</motion.div>
```

---

#### 🖼️ Lucide React (Icons)

**Why Lucide?**
- ✅ Clean, modern icons
- ✅ Consistent design
- ✅ Tree-shakeable (only import what you use)
- ✅ Customizable (size, color, stroke width)

**Example**:
```jsx
import { Search, BookOpen, Download } from 'lucide-react';

<Search className="w-6 h-6 text-gray-600" />
```

**Alternatives Considered**:
- React Icons: Larger bundle, mixed styles
- Font Awesome: Requires separate CSS, heavier

---

#### 🌐 Three.js

**Why Three.js?**
- ✅ 3D graphics in browser
- ✅ WebGL abstraction
- ✅ Visual appeal for homepage

**Use Case**:
- Animated network background on home page

---

#### 📊 Cytoscape.js

**Why Cytoscape?**
- ✅ Purpose-built for graph visualization
- ✅ Powerful layout algorithms (dagre, cose, concentric)
- ✅ Interactive (zoom, pan, click)
- ✅ Customizable styling
- ✅ Large graph support

**Use Case**:
- Citation mesh visualization

**Alternatives Considered**:
- D3.js: Lower-level, steeper learning curve
- Vis.js: Less flexible
- Sigma.js: Less feature-rich

---

### Authentication & Database

#### 🔐 Supabase

**Why Supabase?**
- ✅ PostgreSQL database (familiar SQL)
- ✅ Built-in authentication (email, OAuth)
- ✅ Row-level security (RLS)
- ✅ Real-time subscriptions
- ✅ RESTful API + client SDKs
- ✅ Free tier (perfect for development)
- ✅ One platform for auth + database

**Features Used**:
- **Auth**: Email/password, Google OAuth
- **Database**: PostgreSQL with RLS
- **Storage**: (Future: PDF storage)

**Authentication Flow**:
```
User → Supabase Auth → JWT token → Stored in localStorage
```

**Alternatives Considered**:
- Firebase: Similar, but prefer Supabase's PostgreSQL
- Auth0: Separate service, more complex setup
- Custom auth: Time-consuming, security risks

---

### Export Libraries

#### 📄 jsPDF + jspdf-autotable

**Why jsPDF?**
- ✅ Generate PDFs in browser
- ✅ No server-side processing needed
- ✅ Customizable layouts

**Use Case**:
- Export search results as PDF report

---

#### 📊 xlsx

**Why xlsx?**
- ✅ Generate Excel files in browser
- ✅ Works with all Excel formats
- ✅ Easy API

**Use Case**:
- Export search results as Excel spreadsheet

---

## Backend Technologies

### Web Framework

#### ⚡ FastAPI

**Why FastAPI?**
- ✅ Modern Python framework (Python 3.8+)
- ✅ Automatic API documentation (Swagger UI)
- ✅ Type hints + validation (Pydantic)
- ✅ Async support (concurrent requests)
- ✅ Fast performance (comparable to Node.js, Go)
- ✅ Easy to learn and use
- ✅ Great for data science projects

**Key Features**:
- Automatic request validation
- Automatic response serialization
- Built-in dependency injection
- WebSocket support (future)

**Example**:
```python
@router.get("/search/fetch")
async def fetch_papers(
    topic: str, 
    limit: int = 20
):
    # topic and limit are automatically validated
    # Response is automatically serialized to JSON
    papers = fetch_openalex_papers(topic, limit)
    return {"status": "success", "papers": papers}
```

**Alternatives Considered**:
- Flask: Less features, no async support
- Django: Too heavy, overkill for API
- Node.js/Express: Team prefers Python for data processing

---

#### 🚀 Uvicorn (ASGI Server)

**Why Uvicorn?**
- ✅ Lightning-fast ASGI server
- ✅ Async support
- ✅ WebSocket support
- ✅ Production-ready

**Run Command**:
```bash
uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

---

### Data Validation

#### ✅ Pydantic

**Why Pydantic?**
- ✅ Runtime type checking
- ✅ Automatic data validation
- ✅ Clear error messages
- ✅ Built into FastAPI

**Example**:
```python
from pydantic import BaseModel

class Paper(BaseModel):
    paperId: str
    title: str
    authors: List[str]
    year: Optional[int]
    
# Automatic validation
paper = Paper(
    paperId="W123",
    title="My Paper",
    authors=["Author 1"],
    year="2024"  # ERROR: year must be int
)
```

---

### HTTP Clients

#### 🌐 requests (Synchronous)

**Why requests?**
- ✅ Simple, intuitive API
- ✅ Most popular Python HTTP library
- ✅ Great for simple API calls

**Use Cases**:
- OpenAlex API calls
- OpenRouter API calls
- PDF downloads

---

#### ⚡ aiohttp (Asynchronous)

**Why aiohttp?**
- ✅ Async HTTP client
- ✅ Better performance for multiple requests
- ✅ Non-blocking I/O

**Use Cases**:
- Fetching multiple papers concurrently
- Building citation networks (many API calls)

---

### PDF Processing

#### 📄 pdfplumber

**Why pdfplumber?**
- ✅ High-quality text extraction
- ✅ Preserves layout
- ✅ Extracts tables
- ✅ Pure Python (no system dependencies)

**Use Case**:
- Extract text from research papers for summarization

**Alternative**: PyMuPDF (faster, but C dependency)

---

### Data Processing

#### 🐼 pandas

**Why pandas?**
- ✅ Industry-standard for data manipulation
- ✅ DataFrame structure (tabular data)
- ✅ Easy data cleaning and transformation
- ✅ Great for research data

**Use Cases**:
- Normalizing API responses
- Deduplication
- Batch processing
- Data export

**Example**:
```python
# Fetch multiple sources
openalex_df = fetch_openalex_papers(topic, limit)
arxiv_df = fetch_arxiv_papers(topic, limit)

# Combine and deduplicate
combined_df = pd.concat([openalex_df, arxiv_df])
deduplicated_df = clean_and_deduplicate(combined_df, topic)
```

---

### Database Client

#### 🗄️ supabase-py

**Why supabase-py?**
- ✅ Official Supabase Python client
- ✅ Simple API
- ✅ Automatic authentication
- ✅ Type hints

**Example**:
```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Insert data
response = supabase.table("research_papers").insert({
    "paperid": "W123",
    "title": "My Paper"
}).execute()

# Query data
response = supabase.table("research_papers")\
    .select("*")\
    .eq("topic", "machine learning")\
    .execute()
```

---

### Configuration

#### ⚙️ pydantic-settings

**Why pydantic-settings?**
- ✅ Type-safe configuration
- ✅ Automatic .env loading
- ✅ Validation on startup
- ✅ IDE autocomplete

**Example**:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    OPENROUTER_API_KEY: str
    
    class Config:
        env_file = ".env"

settings = Settings()
# Automatic loading from .env
# Type checking
# Error if required variables missing
```

---

## External Services

### Research Paper APIs

#### 1. OpenAlex API (Primary)

**Why OpenAlex?**
- ✅ **No API key required** (free, open access)
- ✅ Comprehensive coverage (250M+ works)
- ✅ Rich metadata (institutions, fields of study)
- ✅ Citation data (references, cited-by)
- ✅ Open access status
- ✅ Well-documented API
- ✅ Fast and reliable

**Coverage**:
- All academic disciplines
- Books, articles, preprints, datasets
- Author affiliations
- Citation relationships

**Why Primary?**:
- No API key management
- No rate limits (reasonable use)
- Best metadata quality

---

#### 2. arXiv API

**Why arXiv?**
- ✅ Preprints (early access to research)
- ✅ Strong in CS, Physics, Math
- ✅ Full-text PDFs available
- ✅ Free API

**Use Case**:
- Search preprints
- Extract full-text for summarization

---

#### 3. CORE API

**Why CORE?**
- ✅ Open access papers
- ✅ 250M+ papers
- ✅ Full-text access

**Use Case**:
- Additional source for open access papers

---

#### 4. PubMed Central (PMC)

**Why PMC?**
- ✅ Biomedical research
- ✅ Full-text access
- ✅ High-quality papers

**Use Case**:
- Biomedical and health research

---

#### 5. Semantic Scholar

**Why Semantic Scholar?**
- ✅ AI-powered search
- ✅ Citation context
- ✅ Influential citations

**Use Case**:
- Enhanced citation analysis

---

#### 6. Google Scholar (via SerpAPI)

**Why Google Scholar?**
- ✅ Largest coverage
- ✅ Includes books, theses
- ✅ All disciplines

**Why SerpAPI?**
- Google Scholar has no official API
- SerpAPI provides reliable access

**Limitation**: Requires API key, limited free tier

---

### AI/LLM Services

#### 🤖 OpenRouter API (GPT-4o-mini)

**Why OpenRouter?**
- ✅ Single API for multiple LLMs
- ✅ Pay-per-use (cost-effective)
- ✅ No commitment (vs OpenAI subscription)
- ✅ Automatic load balancing
- ✅ Fallback models

**Why GPT-4o-mini?**
- ✅ Cost-effective ($0.15 / 1M input tokens)
- ✅ Fast inference
- ✅ High-quality summaries
- ✅ Large context window (128K tokens)
- ✅ JSON mode (structured output)

**Use Case**:
- Paper summarization (structured summaries)
- Chat with papers (Q&A)

**Alternatives for Future**:
- **BART** (Facebook): Open-source, local deployment
- **PEGASUS** (Google): Purpose-built for summarization
- **FLAN-T5** (Google): Instruction-tuned, versatile
- **Claude** (Anthropic): Longer context, better reasoning

**Why Not Local Models Initially?**
- Hosting costs
- Inference time
- Model management
- Quality vs cost tradeoff

---

## Development Tools

### Version Control

#### 🐙 Git + GitHub

**Why GitHub?**
- ✅ Industry standard
- ✅ Free for public/private repos
- ✅ Pull requests and code review
- ✅ Issues and project management
- ✅ GitHub Actions (CI/CD)
- ✅ Large community

---

### Project Management

#### 📋 Trello

**Why Trello?**
- ✅ Visual kanban boards
- ✅ Simple and intuitive
- ✅ Free tier sufficient
- ✅ Cards, lists, labels
- ✅ Team collaboration

**Columns**:
- Backlog
- To Do
- In Progress
- Review
- Done

---

### Code Editor

#### 💻 VS Code (Recommended)

**Why VS Code?**
- ✅ Free and open-source
- ✅ Excellent extensions
- ✅ Integrated terminal
- ✅ Git integration
- ✅ IntelliSense (autocomplete)
- ✅ Debugging support

**Recommended Extensions**:
- Python
- ESLint
- Prettier
- Tailwind CSS IntelliSense
- GitLens

---

## Architecture Patterns

### Backend Patterns

#### 1. Layered Architecture

```
Routes → Services → CRUD → Database
```

**Benefits**:
- Clear separation of concerns
- Easy to test
- Maintainable
- Scalable

---

#### 2. Dependency Injection

FastAPI's built-in DI:
```python
from fastapi import Depends

def get_db():
    return supabase

@router.get("/papers")
async def get_papers(db = Depends(get_db)):
    return db.table("research_papers").select("*").execute()
```

---

#### 3. Background Tasks

Non-blocking operations:
```python
from fastapi import BackgroundTasks

@router.get("/search")
async def search(background_tasks: BackgroundTasks):
    papers = fetch_papers()
    
    # Store in background (non-blocking)
    background_tasks.add_task(store_papers, papers)
    
    # Return immediately
    return {"papers": papers}
```

---

### Frontend Patterns

#### 1. Component Composition

```
Page → Layout → Components → UI Elements
```

**Benefits**:
- Reusable components
- Easy to maintain
- Testable

---

#### 2. Custom Hooks

Reusable logic:
```jsx
// useAuth.js
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

// Usage
function MyComponent() {
  const { user, signOut } = useAuth();
  // ...
}
```

---

#### 3. Container/Presentational Pattern

```jsx
// Container (logic)
function ResultsContainer() {
  const [papers, setPapers] = useState([]);
  
  useEffect(() => {
    fetchPapers().then(setPapers);
  }, []);
  
  return <ResultsView papers={papers} />;
}

// Presentational (UI)
function ResultsView({ papers }) {
  return (
    <div>
      {papers.map(p => <PaperCard paper={p} />)}
    </div>
  );
}
```

---

## Performance Considerations

### Backend

1. **Async Operations**: Use `async/await` for I/O operations
2. **Batch Processing**: Insert 50 papers at a time
3. **Retry Logic**: Exponential backoff for API failures
4. **Caching** (Future): Redis for frequently accessed data

---

### Frontend

1. **Code Splitting**: React Router lazy loading
2. **Memoization**: `useMemo` for expensive calculations
3. **Virtual Scrolling** (Future): For large result lists
4. **Debouncing**: Search input debouncing
5. **Lazy Loading**: Cytoscape.js loaded on demand

---

## Security Considerations

### Backend

1. **CORS**: Restrict allowed origins
2. **Input Validation**: Pydantic schemas
3. **Environment Variables**: Never commit `.env`
4. **API Key Management**: Secure storage

---

### Frontend

1. **XSS Prevention**: React auto-escapes
2. **HTTPS**: Use HTTPS in production
3. **Auth Tokens**: Stored in localStorage (consider httpOnly cookies)
4. **RLS**: Supabase Row-Level Security

---

## Deployment Strategy

### Development
- Backend: `uvicorn` with `--reload`
- Frontend: `vite` dev server
- Database: Supabase cloud

### Production (Planned)
- Backend: Railway/Heroku (Docker container)
- Frontend: Vercel (static hosting + edge functions)
- Database: Supabase cloud (production tier)
- CDN: Vercel Edge Network

---

## Future Technology Additions

### Short-term (1-3 months)
- [ ] Redis caching layer
- [ ] Celery for background tasks
- [ ] Elasticsearch for full-text search
- [ ] WebSocket for real-time updates

### Medium-term (3-6 months)
- [x] Vector database (Pinecone/Weaviate) for semantic search
- [ ] Local LLM deployment (BART/PEGASUS)
- [ ] Docker containerization
- [ ] CI/CD pipeline (GitHub Actions)

### Long-term (6+ months)
- [ ] Mobile app (React Native)
- [ ] Chrome extension
- [ ] GraphQL API (alternative to REST)
- [ ] Microservices architecture (if needed)

---

## Technology Decision Matrix

| Criteria | React | Vue | Angular |
|----------|-------|-----|---------|
| Learning Curve | ★★★☆☆ | ★★★★☆ | ★★☆☆☆ |
| Performance | ★★★★★ | ★★★★★ | ★★★★☆ |
| Ecosystem | ★★★★★ | ★★★★☆ | ★★★★☆ |
| Team Experience | ★★★★★ | ★★☆☆☆ | ★★☆☆☆ |
| Job Market | ★★★★★ | ★★★★☆ | ★★★★☆ |
| **Total** | **23** | **19** | **16** |

**Winner: React** ✅

---

| Criteria | FastAPI | Flask | Django |
|----------|---------|-------|--------|
| Performance | ★★★★★ | ★★★☆☆ | ★★★☆☆ |
| Documentation | ★★★★★ | ★★★★☆ | ★★★★★ |
| Learning Curve | ★★★★☆ | ★★★★★ | ★★★☆☆ |
| Async Support | ★★★★★ | ★★☆☆☆ | ★★★☆☆ |
| API Features | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| **Total** | **24** | **17** | **18** |

**Winner: FastAPI** ✅

---

## Conclusion

ReSearch Flow's technology stack is carefully chosen to balance:
- **Performance**: Fast, responsive user experience
- **Developer Experience**: Modern tools, great documentation
- **Scalability**: Can handle growth in users and data
- **Cost**: Free/low-cost services for development
- **Team Skills**: Leverages existing Python and JavaScript knowledge
- **Future-proof**: Modern, actively maintained technologies

This stack provides a solid foundation for building a production-ready academic research assistant.

