from mmengine.config import read_base

from ais_bench.benchmark.models import VLLMCustomAPIChat
from ais_bench.benchmark.utils.postprocess.model_postprocessors import extract_non_reasoning_content
from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.datasets import SyntheticDataset, MATHEvaluator, math_postprocess_v2

with read_base():
    from ais_bench.benchmark.configs.summarizers.example import summarizer

# --- synthetic tokenid dataset: 50 requests of exactly 1024 input tokens ---
synthetic_config = {
    "Type": "tokenid",
    "RequestCount": 50,
    "TrustRemoteCode": True,
    "TokenIdConfig": {
        "RequestSize": 1024,
        "PrefixLen": 0,
    },
}

synthetic_datasets = [
    dict(
        abbr="synthetic",
        type=SyntheticDataset,
        config=synthetic_config,
        reader_cfg=dict(input_columns=["question"], output_column="answer"),
        infer_cfg=dict(
            prompt_template=dict(type=PromptTemplate, template="{question}"),
            retriever=dict(type=ZeroRetriever),
            inferencer=dict(type=GenInferencer),
        ),
        eval_cfg=dict(
            evaluator=dict(type=MATHEvaluator, version="v2"),
            pred_postprocessor=dict(type=math_postprocess_v2),
        ),
    )
]
datasets = synthetic_datasets

# --- DeepSeek-V4 service endpoint ---
models = [
    dict(
        attr="service",
        type=VLLMCustomAPIChat,
        abbr="deepseek_v4",
        path="/tok",                      # tokenizer dir (mounted)
        model="deepseek_v4",
        stream=True,                       # stream so TTFT/TPOT are measured
        request_rate=0,                    # 0 = unbounded; concurrency capped by --max-num-workers
        use_timestamp=False,
        retry=2,
        api_key="__AIS_API_KEY__",
        url="https://10.209.20.56/v2/infer/91e911e1-9e11-44fe-acaa-9b826f2391c2/v1",
        enable_ssl=True,
        max_out_len=256,
        batch_size=8,                      # concurrent in-flight requests per worker

        trust_remote_code=True,
        generation_kwargs=dict(temperature=0.01, ignore_eos=True),
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    )
]

work_dir = "/tmp/ais_bench_out/"
