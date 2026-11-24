"""A scripted fake LLM that honours `.with_structured_output(Schema)`."""
from langchain_core.runnables import RunnableLambda


class FakeStructuredLLM:
    def __init__(self, **outputs):
        # outputs keyed by schema class name, e.g. Classification={...}
        self.outputs = outputs
        self.calls: list[str] = []

    def with_structured_output(self, schema):
        def run(_prompt):
            self.calls.append(schema.__name__)
            return schema(**self.outputs[schema.__name__])

        return RunnableLambda(run)
