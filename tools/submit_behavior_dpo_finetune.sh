#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
key_file="$root/openai_ft_api_key.txt"
training_file="$root/generated/laws_behavior_dpo.jsonl"
manifest_file="$root/generated/laws_behavior_manifest.json"
upload_response="$root/generated/laws_behavior_dpo_upload_response.json"
job_response="$root/generated/laws_behavior_dpo_job.json"
model="${OPENAI_FINE_TUNE_MODEL:-gpt-4.1-2025-04-14}"

if [[ ! -f "$key_file" ]]; then
  echo "Missing API key file: $key_file" >&2
  exit 1
fi

if [[ ! -s "$training_file" ]]; then
  echo "Missing or empty DPO training file: $training_file" >&2
  exit 1
fi

if [[ ! -f "$manifest_file" ]]; then
  echo "Missing behavior manifest: $manifest_file" >&2
  exit 1
fi

manifest_hash="$(jq -r '.source_sha256 // empty' "$manifest_file")"
current_hash="$(sha256sum "$root/Laws-of-Robotics.txt" | awk '{print $1}')"
if [[ "$manifest_hash" != "$current_hash" && "${ALLOW_STALE_LAWS_DATASET:-}" != "1" ]]; then
  echo "Refusing to submit stale dataset." >&2
  echo "Manifest source hash: $manifest_hash" >&2
  echo "Current source hash:  $current_hash" >&2
  echo "Rerun tools/generate_law_governed_dataset.py after Laws-of-Robotics.txt stabilizes." >&2
  echo "Set ALLOW_STALE_LAWS_DATASET=1 only if submitting the recorded snapshot is intentional." >&2
  exit 1
fi

api_key="$(tr -d '\r\n' < "$key_file")"

curl -sS https://api.openai.com/v1/files \
  -H "Authorization: Bearer ${api_key}" \
  -F purpose="fine-tune" \
  -F "file=@${training_file}" \
  -o "$upload_response"

file_id="$(jq -r '.id // empty' "$upload_response")"
if [[ -z "$file_id" ]]; then
  echo "Upload failed. Response written to $upload_response" >&2
  jq . "$upload_response" >&2
  exit 1
fi

jq -n --arg training_file "$file_id" --arg model "$model" '{
  training_file: $training_file,
  model: $model,
  suffix: "laws-behavior-dpo",
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
  echo "Fine-tuning job creation failed. Response written to $job_response" >&2
  jq . "$job_response" >&2
  exit 1
fi

jq . "$job_response"
