# LLM Judge Tool

The LLM Judge tool analyzes knowledge base search results and automatically rewrites queries if the results are poor quality.

## Features

- **Automatic Quality Assessment**: Uses LLM to judge if search results are relevant and helpful
- **Query Rewriting**: Automatically rewrites queries when results are poor
- **Retry Logic**: Up to 3 attempts with configurable break times
- **Knowledge Base Integration**: Works with your existing OpenSearch + Jina Embedding setup
- **MLflow Logging**: Comprehensive logging of all knowledge base operations

## Usage

### Basic Usage
```
> using llm_judge with query "machine learning algorithms"
```

### Advanced Usage
```
> using llm_judge with query "python debugging", max_retries=5, break_time=10
```

## Parameters

- **query** (required): The original search query
- **max_retries** (optional, default=3): Maximum number of query rewrite attempts
- **break_time** (optional, default=5): Break time in seconds between retries
- **context_threshold** (optional, default=0.3): Minimum relevance score threshold

## How It Works

1. **Initial Search**: Searches knowledge base with original query
2. **Quality Judgment**: LLM analyzes results for relevance and quality
3. **Query Rewriting**: If results are poor, LLM rewrites the query based on what went wrong
4. **Retry**: Takes a break, then searches again with rewritten query
5. **Final Result**: Returns best results or error if all attempts fail

## Example Output

### Success Case
```json
{
  "status": "success",
  "query": "supervised machine learning classification algorithms",
  "attempt": 2,
  "results": [
    {
      "title": "Random Forest Classification Guide",
      "content": "Random forest is an ensemble learning method...",
      "score": 0.95
    }
  ],
  "judgment": "Results are relevant and helpful"
}
```

### Failure Case
```
Error: All 3 attempts failed. Last query: 'advanced neural network architectures'
```

## Setup Requirements

The tool requires:
- OpenSearch server with knowledge base index
- Jina Embedding API key
- LLM client for judgment and rewriting
- MLflow server for logging (optional)

## Configuration

Set these environment variables:
- `OPENSEARCH_HOST`, `OPENSEARCH_PORT`, `OPENSEARCH_SSL`
- `OPENSEARCH_USER`, `OPENSEARCH_PASSWORD` (optional)
- `JINA_API_KEY`, `JINA_BASE_URL`
- `API_KEY`, `BASE_URL` (for LLM client)
- `MLFLOW_TRACKING_URI`: MLflow server URL (default: http://localhost:5000)
- `MLFLOW_EXPERIMENT_NAME`: Experiment name (default: KnowledgeBase)

# Global MLflow Integration

Complete MLflow tracking for your entire AI agent codebase - not just retrieval operations!

## 🎯 What It Tracks

### **All Tool Executions**
- Every tool call with parameters and results
- Execution time and performance metrics
- Error tracking and failure rates
- Result size and type analysis

### **Agent Sessions**
- Complete user-agent interactions
- Tools used per session
- Session duration and performance
- Conversation history tracking

### **LLM API Calls**
- Model usage and token consumption
- Response time metrics
- Message content (sanitized)
- Cost tracking potential

### **Knowledge Base Operations**
- Search queries and results
- Judgment scores and reasoning
- Query rewrite operations
- Performance metrics

### **Error Tracking**
- Error types and messages
- Context information
- Error frequency analysis
- Debugging artifacts

### **Performance Metrics**
- Custom metrics tracking
- System performance indicators
- Usage statistics
- Success/failure rates

## 🚀 Quick Start

### **1. Basic Integration**
```python
from mlflow.global_tracker import GlobalMLflowTracker

# Initialize in your session
tracker = GlobalMLflowTracker(config)
tracker.setup_experiment({
    "environment": "production",
    "version": "1.0.0"
})
```

### **2. Automatic Tool Tracking**
```python
from mlflow.global_tracker import track_tool

class MyTool(Tool):
    @track_tool("my_tool_name")  # Automatic tracking!
    async def execute(self, invocation):
        # Your tool logic here
        return result
```

### **3. Manual Tracking**
```python
from mlflow.global_tracker import track_operation

# Track any operation
with track_operation("custom_operation", tracker):
    # Your code here
    pass
```

## 📊 Usage Examples

### **Session Integration**
```python
# In your Session class
class Session:
    def __init__(self, config):
        self.mlflow_tracker = GlobalMLflowTracker(config)
        
    def handle_user_message(self, message):
        start_time = time.time()
        
        # Process message
        response = self.process_message(message)
        tools_used = self.get_tools_used()
        
        # Track the interaction
        self.track_agent_interaction(
            user_message=message,
            agent_response=response,
            tools_used=tools_used,
            session_duration=time.time() - start_time
        )
        
        return response
```

### **LLM Call Tracking**
```python
# Track LLM API calls
def call_llm(self, messages):
    start_time = time.time()
    response = self.llm_client.chat_completion(messages)
    response_time = time.time() - start_time
    
    # Track the call
    self.track_llm_call(
        model=self.config.model,
        messages=messages,
        response=response.content,
        tokens_used=response.usage.total_tokens,
        response_time=response_time
    )
    
    return response
```

### **Error Tracking**
```python
try:
    result = risky_operation()
except Exception as e:
    # Track the error
    self.track_error(
        error_type="OperationFailed",
        error_message=str(e),
        context={"operation": "risky_operation", "user": session.user_id}
    )
    raise
```

### **Performance Metrics**
```python
# Track custom performance metrics
metrics = {
    "cpu_usage": 75.5,
    "memory_usage": 60.2,
    "response_time_ms": 1250,
    "queue_length": 5
}

self.mlflow_tracker.track_performance_metrics(metrics)
```

## 🛠️ Configuration

### **Environment Variables**
```bash
# MLflow Configuration
export MLFLOW_TRACKING_URI="http://localhost:5000"
export MLFLOW_EXPERIMENT_NAME="AIAgent"

# Optional: Custom experiment naming
export MLFLOW_ENVIRONMENT="production"
export MLFLOW_VERSION="1.0.0"
```

### **Config Integration**
```python
# In config/config.py
@property
def mlflow_tracking_uri(self) -> str:
    return os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")

@property
def mlflow_experiment_name(self) -> str:
    return os.environ.get("MLFLOW_EXPERIMENT_NAME", "AIAgent")
```

## 📈 What Gets Logged

### **Artifacts Stored**
- `session_*.json` - Complete session data
- `tool_*.json` - Tool execution details
- `llm_call_*.json` - LLM API call logs
- `error_*.json` - Error details and context
- `metrics_*.json` - Performance metrics

### **Parameters Tracked**
- Tool names and parameters
- Model names and configurations
- Session metadata
- Environment settings

### **Metrics Captured**
- Execution times
- Token usage
- Success/failure rates
- Performance indicators
- Error counts

## 🎛️ Advanced Features

### **Decorator-Based Tracking**
```python
from mlflow.global_tracker import track_tool

class SearchTool(Tool):
    @track_tool("knowledge_search")
    async def execute(self, invocation):
        # Automatically tracked!
        return await self.search(invocation.params['query'])

class RewriteTool(Tool):
    @track_tool("query_rewrite")
    async def execute(self, invocation):
        # Automatically tracked!
        return await self.rewrite(invocation.params['query'])
```

### **Context Manager Tracking**
```python
from mlflow.global_tracker import track_operation

# Track any code block
with track_operation("database_migration", tracker):
    migrate_database()
    
# Track file operations
with track_operation("file_processing", tracker):
    process_large_file()
    
# Track API calls
with track_operation("external_api", tracker):
    response = external_client.call_api()
```

### **Selective Tracking**
```python
# Enable/disable tracking
tracker.enable_tracking()
tracker.disable_tracking()

# Check tracking status
if tracker.tracking_enabled:
    tracker.track_tool_execution(...)
```

## 🔍 MLflow UI Access

### **View Experiments**
```bash
# Start MLflow UI
mlflow ui

# Access at http://localhost:5000
```

### **What You'll See**
- **Experiments**: Different experiment runs
- **Runs**: Individual tool executions and sessions
- **Metrics**: Performance charts over time
- **Artifacts**: Downloadable logs and data
- **Parameters**: Configuration and input data

### **Dashboard Examples**
- Tool execution frequency
- Average response times
- Error rates by tool
- Token usage trends
- Session duration patterns

## 📊 Monitoring & Analysis

### **Key Metrics to Track**
1. **Performance**: Response times, throughput
2. **Quality**: Success rates, error frequencies
3. **Usage**: Tool popularity, session patterns
4. **Cost**: Token usage, API call costs
5. **Reliability**: Error rates, system health

### **Alerting Setup**
```python
# Monitor error rates
if tracker.get_session_stats()['error_count'] > threshold:
    send_alert("High error rate detected")

# Monitor performance
if avg_response_time > sla_threshold:
    send_alert("Performance SLA violation")
```

## 🛡️ Privacy & Security

### **Data Sanitization**
- Sensitive parameters automatically redacted
- API keys, passwords, tokens masked
- Content length limits applied
- PII filtering available

### **Configurable Privacy**
```python
# Custom sanitization rules
def custom_sanitize(params):
    sensitive_keys = ['user_data', 'personal_info']
    # Your custom logic here
    return sanitized_params

tracker.set_sanitizer(custom_sanitize)
```

## 🔄 Integration Patterns

### **Agent Integration**
```python
class AIAgent:
    def __init__(self, config):
        self.session = Session(config)  # Includes MLflow tracker
        
    async def process_request(self, request):
        start_time = time.time()
        
        try:
            response = await self.handle_request(request)
            
            # Track successful interaction
            self.session.track_agent_interaction(
                user_message=request.message,
                agent_response=response,
                tools_used=self.get_tools_used(),
                session_duration=time.time() - start_time
            )
            
        except Exception as e:
            # Track error
            self.session.track_error(
                error_type="ProcessingError",
                error_message=str(e),
                context={"request_id": request.id}
            )
            raise
```

### **Tool Registry Integration**
```python
# All tools automatically tracked
class ToolRegistry:
    def get_tools(self):
        tools = [
            SearchTool(),
            RewriteTool(),
            JudgeTool(),
            # All will have @track_tool decorators
        ]
        return tools
```

## 🚀 Production Deployment

### **Best Practices**
1. **Enable in production** for comprehensive monitoring
2. **Set retention policies** for artifacts
3. **Configure alerts** for critical metrics
4. **Monitor storage usage** for artifacts
5. **Regular backup** of MLflow database

### **Scaling Considerations**
- **Async logging** for minimal performance impact
- **Batch artifact uploads** for efficiency
- **Configurable tracking levels** (debug vs production)
- **Distributed tracking** across multiple instances

Your entire AI agent codebase now has **comprehensive MLflow tracking** for complete observability! 🎉
