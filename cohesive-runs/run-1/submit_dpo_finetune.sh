#!/usr/bin/env bash
set -euo pipefail

run_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$run_dir/../.." && pwd)"
api_key="$(tr -d '\r\n' < "$root/openai_ft_api_key.txt")"
training_file="$run_dir/training_dpo.jsonl"
upload_response="$run_dir/dpo_upload_response.json"
job_response="$run_dir/dpo_finetune_job.json"
model="${OPENAI_FINE_TUNE_MODEL:-gpt-4.1-2025-04-14}"

if [[ ! -s "$training_file" ]]; then
  echo "Missing or empty DPO training file: $training_file" >&2
  exit 1
fi

curl -sS https://api.openai.com/v1/files \
  -H "Authorization: Bearer ${api_key}" \
  -F purpose="fine-tune" \
  -F "file=@${training_file}" \
  -o "$upload_response"

file_id="$(jq -r '.id // empty' "$upload_response")"
if [[ -z "$file_id" ]]; then
  echo "Upload failed:" >&2
  jq . "$upload_response" >&2
  exit 1
fi

jq -n --arg training_file "$file_id" --arg model "$model" '{
  training_file: $training_file,
  model: $model,
  suffix: "cohesive-run-1-dpo",
  method: {
    type: "dpo",
    dpo: {
      hyperparameters: {
        beta: "auto"
      }
    }
  }
}' | curl -sS https://api.openai.com/v1/fine_tuning/jobs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${api_key}" \
  -d @- \
  -o "$job_response"

job_id="$(jq -r '.id // empty' "$job_response")"
if [[ -z "$job_id" ]]; then
  echo "Fine-tuning job creation failed:" >&2
  jq . "$job_response" >&2
  exit 1
fi

jq . "$job_response"
