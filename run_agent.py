#!/usr/bin/env python3
"""
HealthCoachAI Agent Runner

Runs the HealthCoachAI agent in AgentCore Runtime environment.
"""

import os
import sys

# Set environment variables (configure as needed)
# os.environ['HEALTH_STACK_NAME'] = 'YOUR_CLOUDFORMATION_STACK_NAME'

# Run the agent
if __name__ == "__main__":
    from health_coach_ai.agent import app
    
    print("Starting HealthCoachAI Agent...")
    print("Running in AgentCore Runtime environment")
    print("=" * 50)
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nAgent stopped")
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)