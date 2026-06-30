import json
import pytest
from unittest.mock import AsyncMock, patch
from google.genai import types
from aggregator_engine import ThinkingAggregatorAgent, ThinkingAggregatorReport

def test_clean_context_bloat():
    # Instantiate the agent with dummy data
    agent = ThinkingAggregatorAgent([])
    
    # Test case 1: Context logs and system prompt headers
    input_text = "[CONTEXT_LOG] Connection established. [SYSTEM_PROMPT] System active. Action: pause subscription"
    expected = "Connection established.  System active. Action: pause subscription"
    assert agent.clean_context_bloat(input_text) == expected
    
    # Test case 2: Markdown code block structures and confidence metrics
    input_text2 = "```json\n{\"intent\": \"pause\"}\n```\nConfidence: 0.95"
    expected2 = "{\"intent\": \"pause\"}"
    assert agent.clean_context_bloat(input_text2) == expected2


def test_grouping_and_deduplication():
    # Provide parallel agent outputs with duplicate text and low-weight findings
    raw_data = [
        {
            "category": "user_intent",
            "raw_text": "[CONTEXT_LOG] User wants to pause subscription",
            "weight": 0.95
        },
        {
            "category": "user_intent",
            "raw_text": "User wants to pause subscription", # Duplicate after cleaning
            "weight": 0.85
        },
        {
            "category": "user_intent",
            "raw_text": "User wants to terminate service", # Conflict
            "weight": 0.60
        },
        {
            "category": "system_status",
            "raw_text": "Service is offline",
            "weight": 0.15 # Low weight, should be pruned
        }
    ]
    
    # Test grouping & deduplication internal logic (Step 1 of process)
    # We will simulate this by checking how grouped_conflicts are structured inside a test
    agent = ThinkingAggregatorAgent(raw_data)
    
    grouped_conflicts = {}
    for entry in agent.raw_data:
        category = entry.get("category", "unassigned").strip().lower()
        raw_text = entry.get("raw_text", "")
        weight = entry.get("weight", 0.0)

        clean_text = agent.clean_context_bloat(raw_text)
        if not clean_text or weight < 0.2:
            continue

        if category not in grouped_conflicts:
            grouped_conflicts[category] = []
        
        if not any(clean_text.lower() == existing['text'].lower() for existing in grouped_conflicts[category]):
            grouped_conflicts[category].append({
                "text": clean_text,
                "weight": weight
            })
            
    # Assert 'system_status' is pruned because weight is < 0.2
    assert "system_status" not in grouped_conflicts
    
    # Assert 'user_intent' contains two elements (one is deduplicated)
    assert len(grouped_conflicts["user_intent"]) == 2
    assert grouped_conflicts["user_intent"][0]["text"] == "User wants to pause subscription"
    assert grouped_conflicts["user_intent"][1]["text"] == "User wants to terminate service"


def test_fallback_parse_json():
    agent = ThinkingAggregatorAgent([])
    
    # Mangled JSON with no outer brackets or extra text
    mangled_response = (
        "Here is the result:\n"
        "{\"category\": \"user_intent\", \"resolved_data\": \"User wants to pause service\", \"confidence_score\": 0.95}\n"
        "Some other logs here."
    )
    
    parsed = agent.fallback_parse_json(mangled_response)
    assert "findings" in parsed
    assert len(parsed["findings"]) == 1
    assert parsed["findings"][0]["category"] == "user_intent"
    assert parsed["findings"][0]["resolved_data"] == "User wants to pause service"
    assert parsed["findings"][0]["confidence_score"] == 0.95


@pytest.mark.asyncio
async def test_process_with_mocked_judge():
    raw_data = [
        {"category": "user_intent", "raw_text": "User wants to pause subscription", "weight": 0.9}
    ]
    
    agent = ThinkingAggregatorAgent(raw_data)
    
    # Mocking the runner and LLM response to simulate the Judge agent
    mock_runner_instance = AsyncMock()
    
    # Create mock event for InMemoryRunner (is_final_response is synchronous)
    from unittest.mock import MagicMock
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    
    # Mock Content and Part structure
    mock_part = MagicMock()
    mock_part.text = """
    <thinking>
    - Found user wants to pause.
    - Highest weight is 0.9.
    </thinking>
    ```json
    {
      "findings": [
        {
          "category": "user_intent",
          "resolved_data": "Pause user subscription",
          "confidence_score": 0.90
        }
      ]
    }
    ```
    """
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    mock_event.content = mock_content
    
    # We yield the final response event
    async def mock_run_async(*args, **kwargs):
        yield mock_event
        
    mock_runner_instance.run_async = mock_run_async
    
    with patch('aggregator_engine.InMemoryRunner', return_value=mock_runner_instance):
        report_str = await agent.process()
        report = json.loads(report_str)
        
        assert "thinking_process" in report
        assert "findings" in report
        assert report["findings"][0]["category"] == "user_intent"
        assert report["findings"][0]["resolved_data"] == "Pause user subscription"
        assert report["findings"][0]["confidence_score"] == 0.90
