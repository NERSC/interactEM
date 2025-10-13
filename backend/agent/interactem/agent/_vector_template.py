VECTOR_CONFIG_TEMPLATE = """sources:
  operator_logs:
    type: file
    include:
      - {{ logs_dir }}/*/op-*.log
    read_from: beginning

  vector_logs:
    type: internal_logs

  agent_logs:
    type: file
    include:
      - {{ logs_dir }}/agent.log
    read_from: beginning

transforms:
  parse_operator_logs:
    type: remap
    inputs:
      - operator_logs
    source: |
{% raw %}
      # Parse the k8s format: TIMESTAMP stdout|stderr FLAGS LOG_CONTENT
      # Timestamp is in RFC3339 format: 2025-10-07T19:58:32.567014468-04:00
      parsed = parse_regex!(.message, r'^(?P<timestamp>[^ ]+) (?P<stream>stdout|stderr) (?P<flags>[^ ]+) (?P<log>.*)$')
      .stream = parsed.stream

      # Use the K8s timestamp (already in RFC3339/ISO 8601 format)
      k8s_time, time_err = parse_timestamp(parsed.timestamp, format: "%+")
      if time_err == null {
        .timestamp = k8s_time
      }

      # Extract deployment_id and operator_id from the file path
      # Format: {{ logs_dir }}/<deployment_id>/op-<operator_id>.log
      file_match = parse_regex!(string!(.file), r'/(?P<deployment_id>[^/]+)/op-(?P<operator_id>[^.]+)\\.log$')
      .deployment_id = file_match.deployment_id
      .operator_id = file_match.operator_id
{% endraw %}
      .agent_id = "{{ agent_id }}"
{% raw %}
      .log_type = "operator"

      # Parse the Python logging format from the log content
      # Format: ISO8601_TIMESTAMP - module.name - LEVEL - message
      # Example: 2025-10-08T13:02:06.547Z - module.name - INFO - message
      log_match, err = parse_regex(parsed.log, r'^(?P<log_timestamp>[^ ]+) - (?P<module>[^ ]+) - (?P<level>[^ ]+) - (?P<message>.+)$')
      if err == null {
        .module = log_match.module
        .level = log_match.level
        .log = log_match.message
      } else {
        # If parsing fails, this is likely a print() statement or unstructured output
        # Mark it as such and keep the original content
        .log = parsed.log
        .level = "PRINT"
        .module = "unknown"
      }

      # Remove the original message field to avoid duplication
      del(.message)
{% endraw %}

  parse_vector_logs:
    type: remap
    inputs:
      - vector_logs
    source: |
{% raw %}
      # internal_logs already provides structured data with message, timestamp, etc.
      # Just rename message to log for consistency and add metadata
      .log = string!(.message)
{% endraw %}
      .agent_id = "{{ agent_id }}"
      .log_type = "vector"
{% raw %}
      # Remove the original message field to avoid duplication
      del(.message)
{% endraw %}

  parse_agent_logs:
    type: remap
    inputs:
      - agent_logs
    source: |
{% raw %}
      # Agent logs come from Python logging with ANSI color codes
      # Agent ID is known from the directory structure
{% endraw %}
      .agent_id = "{{ agent_id }}"
{% raw %}
      .log_type = "agent"

      # Strip ANSI color codes from the message
      .log = replace(string!(.message), r'\\x1b\\[[0-9;]*m', "")

      # Parse the Python logging format: ISO8601_TIMESTAMP - module.name - LEVEL - message
      # Example: 2025-10-08T13:02:06.547Z - module.name - INFO - message
      log_match, err = parse_regex(.log, r'^(?P<timestamp>[^ ]+) - (?P<module>[^ ]+) - (?P<level>[^ ]+) - (?P<message>.+)$')
      if err == null {
        # Parse the ISO 8601 timestamp (RFC3339 format with %+ in Vector)
        parsed_time, time_err = parse_timestamp(log_match.timestamp, format: "%+")
        if time_err == null {
          .timestamp = parsed_time
        }
        .module = log_match.module
        .level = log_match.level
        .log = log_match.message
      } else {
        # If parsing fails, this is likely a print() statement or unstructured output
        # Mark it as such and keep the original content
        .level = "PRINT"
        .module = "unknown"
        # .log already has the content with ANSI codes stripped
      }

      # Remove the original message field to avoid duplication
      del(.message)
{% endraw %}

sinks:
  vector_aggregator:
    type: vector
    inputs:
      - parse_operator_logs
      - parse_vector_logs
      - parse_agent_logs
    address: {{ vector_addr }}
    version: '2'
"""
