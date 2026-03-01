"""Worker GPU 5 (3080-main)"""
import os, sys, json, torch, traceback
from pathlib import Path
from datetime import datetime

os.environ["CUDA_VISIBLE_DEVICES"] = "5"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# CVE-2025-32434 bypass
import transformers.utils.import_utils
transformers.utils.import_utils.check_torch_load_is_safe = lambda: None
import transformers.trainer
transformers.trainer.check_torch_load_is_safe = lambda: None

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Patches bitsandbytes
try:
    import bitsandbytes as bnb
    _orig_new = bnb.nn.Params4bit.__new__
    @staticmethod
    def _p_new(cls, data=None, requires_grad=True, **kw):
        kw.pop("_is_hf_initialized", None)
        return _orig_new(cls, data=data, requires_grad=requires_grad, **kw)
    bnb.nn.Params4bit.__new__ = _p_new

    _orig_as_dict = bnb.functional.QuantState.as_dict
    def _p_as_dict(self, packed=False):
        if self.nested and hasattr(self, "offset") and self.offset is not None and self.offset.is_meta:
            self.offset = torch.tensor(0.0)
        return _orig_as_dict(self, packed=packed)
    bnb.functional.QuantState.as_dict = _p_as_dict

    _NF4 = torch.tensor([-1.0,-0.6962,-0.5251,-0.3949,-0.2844,-0.1848,-0.0911,0.0,0.0796,0.1609,0.2461,0.3379,0.4407,0.5626,0.7230,1.0], dtype=torch.float32)
    _orig_to = bnb.functional.QuantState.to
    def _p_to(self, device):
        if hasattr(self,"code") and self.code is not None and self.code.is_meta:
            self.code = _NF4.clone().to(device)
        if hasattr(self,"absmax") and self.absmax is not None and self.absmax.is_meta:
            self.absmax = torch.zeros(self.absmax.shape, dtype=self.absmax.dtype, device=device)
        if self.nested:
            if hasattr(self,"offset") and self.offset is not None and self.offset.is_meta:
                self.offset = torch.tensor(0.0, device=device)
            if hasattr(self,"state2") and self.state2 is not None:
                if hasattr(self.state2,"code") and self.state2.code is not None and self.state2.code.is_meta:
                    self.state2.code = _NF4.clone().to(device)
                if hasattr(self.state2,"absmax") and self.state2.absmax is not None and self.state2.absmax.is_meta:
                    self.state2.absmax = torch.zeros(self.state2.absmax.shape, dtype=self.state2.absmax.dtype, device=device)
        return _orig_to(self, device)
    bnb.functional.QuantState.to = _p_to
    print("[PATCH] bitsandbytes OK")
except Exception as e:
    print(f"[WARN] {e}")

MODEL = "Qwen/Qwen3-8B"
TRAIN_FILE = r"F:\BUREAU\turbo\finetuning\dataset\jarvis_final_train.jsonl"
EVAL_FILE = r"F:\BUREAU\turbo\finetuning\dataset\jarvis_final_eval.jsonl"
OUTPUT_DIR = Path(r"F:/BUREAU/turbo/finetuning/output")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
run_name = f"jarvis-qwen3-8b-3080-main-{timestamp}"

resume_ckpt = None
output_dir = str(OUTPUT_DIR / run_name)
print(f"[FRESH] {run_name}")


def main():
    print(f"\n===== GPU 5 (3080-main) =====")
    print(f"  Steps: 500 | Seq: 1024 | Batch: 1x8 | LoRA r=16")

    # Unload LM Studio
    try:
        import subprocess as sp
        sp.run(["C:/Users/franc/.lmstudio/bin/lms.exe","unload","--all"], capture_output=True, timeout=5)
    except: pass

    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
    from trl import SFTTrainer, SFTConfig
    from datasets import load_dataset

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        llm_int8_enable_fp32_cpu_offload=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True, padding_side="right")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    n = torch.cuda.device_count()
    max_memory = {}
    for i in range(n):
        vram = torch.cuda.get_device_properties(i).total_mem / (1024**3) if hasattr(torch.cuda.get_device_properties(i), 'total_mem') else torch.cuda.get_device_properties(i).total_memory / (1024**3)
        max_memory[i] = f"{int(vram * 0.85)}GiB"
        print(f"  GPU {i}: {torch.cuda.get_device_name(i)} -- {vram:.1f} GB")
    max_memory["cpu"] = "20GiB"

    # Force single GPU (no offload = no meta tensor crash)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    print(f"[OK] Model: {model.get_memory_footprint()/1024**3:.1f} GB")

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora_config = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05,
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
        bias="none", task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    t, total = model.get_nb_trainable_parameters()
    print(f"[OK] LoRA r=16: {t:,} trainables ({100*t/total:.2f}%)")

    files = {"train": TRAIN_FILE}
    if EVAL_FILE:
        files["test"] = EVAL_FILE
    ds = load_dataset("json", data_files=files)
    print(f"[OK] Train: {len(ds['train'])}")
    has_eval = "test" in ds

    args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=3,
        max_steps=500,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        weight_decay=0.01,
        warmup_ratio=0.05,
        max_grad_norm=0.3,
        logging_steps=10,
        save_steps=50,
        eval_strategy="steps" if has_eval else "no",
        eval_steps=100 if has_eval else None,
        save_total_limit=3,
        fp16=False,
        bf16=True,    # FIX: bf16 partout — pas de GradScaler = pas de crash Turing
        max_length=1024,
        packing=False,
        run_name=run_name,
        report_to="none",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        seed=42,
        dataloader_pin_memory=True,
        dataloader_num_workers=0,
        remove_unused_columns=False,
    )

    trainer = SFTTrainer(
        model=model, args=args,
        train_dataset=ds["train"],
        eval_dataset=ds.get("test"),
        processing_class=tokenizer,
    )

    print(f"[>>>] Training GPU 5 (3080-main) -- 500 steps...")
    result = trainer.train(resume_from_checkpoint=resume_ckpt)

    final = os.path.join(output_dir, "final")
    trainer.save_model(final)
    tokenizer.save_pretrained(final)

    metrics = result.metrics
    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n[DONE] GPU 5 (3080-main): loss={metrics.get('train_loss','?')} runtime={metrics.get('train_runtime',0):.0f}s")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[CRASH] GPU 5 (3080-main): {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)
