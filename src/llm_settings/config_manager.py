#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Configuration Manager
複数のLLMプロバイダー（OpenAI、Claude、DeepSeek、ローカルLLM、OpenRouter、Gemini）を
統一的に管理・切り替えるための設定システム
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum
import requests
from abc import ABC, abstractmethod
import time, random, threading, functools

class LLMProvider(Enum):
    """サポートされるLLMプロバイダー"""
    OPENAI = "openai"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"
    LOCAL = "local"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    GEMINI = "gemini"

class MinIntervalRateLimiter:
    def __init__(self, min_interval_sec: float = 0.7):
        self.min_interval = float(min_interval_sec)
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            delay = self.min_interval - elapsed
            if delay > 0:
                time.sleep(delay + random.random() * 0.15)
            self._last_call = time.monotonic()

LLM_RATE_LIMITER = MinIntervalRateLimiter(min_interval_sec=0.7)

class LLMConfig:
    """LLM設定を管理するクラス"""
    
    def __init__(self, config_path: Path = None):
        """
        Args:
            config_path: 設定ファイルのパス（デフォルト: src/llm_settings/llm_config.json）
        """
        if config_path is None:
            config_path = Path(__file__).parent / "llm_config.json"
        
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
    
    def _get_default_gpt5_options(self) -> Dict[str, Any]:
        """GPT-5系モデル用の詳細パラメータのデフォルト値"""
        return {
            "reasoning_effort": "minimal",  # minimal / low / medium / high
            "reasoning_summary": None,       # auto / concise / detailed
            "verbosity": "medium",          # low / medium / high
            "response_format": "text",
            "max_output_tokens": 2048,
            "metadata": {},
            "cache_control_type": "none",  # none / prompt / ephemeral
            "cache_control_ttl_seconds": None,
            "store": True,
            "include": [],
            "parallel_tool_calls": None,
            "tool_choice": None,
            "tools": [],
            "service_tier": None,
            "truncation": None,
            "user": None,
            "background": None,
            "extra": {}
        }

    def _ensure_gpt5_defaults(self, openai_cfg: Dict[str, Any]):
        """既存設定にGPT-5用パラメータが無い場合、デフォルトを補完"""
        defaults = self._get_default_gpt5_options()
        gpt5_options = openai_cfg.setdefault("gpt5_options", {})
        deprecated_keys = {
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "logit_bias"
        }
        for key in list(gpt5_options.keys()):
            if key in deprecated_keys:
                gpt5_options.pop(key, None)
        if "text_verbosity" in gpt5_options and "verbosity" not in gpt5_options:
            gpt5_options["verbosity"] = gpt5_options.pop("text_verbosity")
        include_value = gpt5_options.get("include")
        if include_value is None:
            gpt5_options["include"] = []
        elif not isinstance(include_value, list):
            gpt5_options["include"] = [include_value]
        tools_value = gpt5_options.get("tools")
        if tools_value is None:
            gpt5_options["tools"] = []
        for key, value in defaults.items():
            if key not in gpt5_options:
                gpt5_options[key] = value

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込む"""
        if not self.config_path.exists():
            # デフォルト設定を作成
            default_config = self._create_default_config()
            self._save_config(default_config)
            return default_config
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # 既存の設定にGeminiがない場合は追加
        providers = config.get("providers", {})
        if "gemini" not in providers:
            providers["gemini"] = self._get_default_gemini_config()
            self._save_config(config)

        openai_cfg = providers.get("openai")
        if openai_cfg is not None:
            prev_options = json.dumps(openai_cfg.get("gpt5_options", {}), sort_keys=True)
            self._ensure_gpt5_defaults(openai_cfg)
            if json.dumps(openai_cfg.get("gpt5_options", {}), sort_keys=True) != prev_options:
                self._save_config(config)

        gemini_cfg = providers.get("gemini")
        if gemini_cfg is not None:
            prev_options = json.dumps(gemini_cfg.get("gemini_options", {}), sort_keys=True)
            self._ensure_gemini_defaults(gemini_cfg)
            if json.dumps(gemini_cfg.get("gemini_options", {}), sort_keys=True) != prev_options:
                self._save_config(config)

        return config
    
    def _get_default_gemini_options(self) -> Dict[str, Any]:
        """Gemini 2.5/3系モデル用の詳細パラメータのデフォルト値"""
        return {
            "thinking_level": "low",            # Gemini 3用: minimal/low/medium/high
            "thinking_budget": 1024,            # Gemini 2.5用: 0=無効(Flashのみ), -1=動的, 1024=low, 8192=medium, 24576=high
            "response_mime_type": "application/json",
            "candidate_count": 1,
            "safety_settings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        }

    def _ensure_gemini_defaults(self, gemini_cfg: Dict[str, Any]):
        """既存設定にGemini用パラメータが無い場合、デフォルトを補完"""
        defaults = self._get_default_gemini_options()
        gemini_options = gemini_cfg.setdefault("gemini_options", {})
        # 旧形式のトップレベルキーをgemini_optionsに移行
        # storeは新SDKでは不要なので移行対象外
        for legacy_key in ("response_mime_type", "candidate_count", "safety_settings"):
            if legacy_key in gemini_cfg and legacy_key not in gemini_options:
                gemini_options[legacy_key] = gemini_cfg.pop(legacy_key)
            elif legacy_key in gemini_cfg:
                gemini_cfg.pop(legacy_key)
        for key, value in defaults.items():
            if key not in gemini_options:
                gemini_options[key] = value

    def _get_default_gemini_config(self) -> Dict[str, Any]:
        """Geminiのデフォルト設定を取得"""
        return {
            "api_key": "",
            "model": "gemini-2.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "temperature": 1.0,
            "max_tokens": 8192,
            "timeout": 120,
            "gemini_options": self._get_default_gemini_options(),
        }
    
    def _create_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を作成"""
        return {
            "active_provider": "openai",
            "providers": {
                "openai": {
                    "api_key": "",
                    "model": "gpt-4o-mini",
                    "base_url": "https://api.openai.com/v1",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "timeout": 60,
                    "gpt5_options": self._get_default_gpt5_options()
                },
                "claude": {
                    "api_key": "",
                    "model": "claude-3-opus-20240229",
                    "base_url": "https://api.anthropic.com",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "timeout": 60
                },
                "deepseek": {
                    "api_key": "",
                    "model": "deepseek-chat",
                    "base_url": "https://api.deepseek.com",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "timeout": 60
                },
                "local": {
                    "base_url": "http://localhost:8000/v1",
                    "model": "llama3:8b",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "timeout": 120,
                    "response_format": {"type": "json_object"}
                },
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "model": "llama3:8b",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "timeout": 120
                },
                "openrouter": {
                    "api_key": "",
                    "model": "openrouter/horizon-beta",
                    "base_url": "https://openrouter.ai/api/v1",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "timeout": 60,
                    "site_url": "",
                    "site_name": ""
                },
                "gemini": self._get_default_gemini_config()  # 追加
            },
            "retry_config": {
                "max_retries": 3,
                "retry_delay": 2,
                "exponential_backoff": True
            }
        }
    
    def _save_config(self, config: Dict[str, Any]):
        """設定をファイルに保存"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def _validate_config(self):
        """設定の妥当性をチェック"""
        active = self.config.get("active_provider")
        if active not in [p.value for p in LLMProvider]:
            raise ValueError(f"Invalid active_provider: {active}")
        
        if active not in self.config.get("providers", {}):
            raise ValueError(f"Active provider {active} not found in providers config")
    
    def get_active_provider(self) -> str:
        """現在アクティブなプロバイダーを取得"""
        return self.config["active_provider"]
    
    def set_active_provider(self, provider: str):
        """アクティブなプロバイダーを設定"""
        if provider not in [p.value for p in LLMProvider]:
            raise ValueError(f"Invalid provider: {provider}")
        
        self.config["active_provider"] = provider
        self._save_config(self.config)
    
    def get_provider_config(self, provider: str = None) -> Dict[str, Any]:
        """指定されたプロバイダーの設定を取得"""
        if provider is None:
            provider = self.get_active_provider()
        
        return self.config["providers"].get(provider, {})
    
    def update_provider_config(self, provider: str, **kwargs):
        """プロバイダーの設定を更新"""
        if provider not in self.config["providers"]:
            raise ValueError(f"Provider {provider} not found")
        
        self.config["providers"][provider].update(kwargs)
        self._save_config(self.config)
    
    def set_api_key(self, provider: str, api_key: str):
        """APIキーを設定"""
        self.update_provider_config(provider, api_key=api_key)
    
    def get_retry_config(self) -> Dict[str, Any]:
        """リトライ設定を取得"""
        return self.config.get("retry_config", {})


class BaseLLMClient(ABC):
    """LLMクライアントの基底クラス"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """チャット補完を実行"""
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """接続の妥当性を検証"""
        pass

    def get_effective_params(self) -> Dict[str, Any]:
        """実際にAPIに送信されるパラメータを返す（サブクラスでオーバーライド可）"""
        return {
            "model": self.config.get("model", "(不明)"),
            "temperature": self.config.get("temperature", 0.0),
            "max_tokens": self.config.get("max_tokens", 4096),
            "timeout": self.config.get("timeout", 120),
        }


class OpenAIClient(BaseLLMClient):
    """OpenAI API クライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import openai
        self.client = openai.OpenAI(
            api_key=config.get("api_key"),
            base_url=config.get("base_url")
        )
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """OpenAI APIでチャット補完を実行"""
        try:
            model_name = self.config.get("model", "gpt-4o-mini")
            if model_name.startswith("gpt-5"):
                gpt5_opts = self.config.get("gpt5_options", {})

                # Responses API を使用
                cache_type = gpt5_opts.get("cache_control_type", "none")
                cache_ttl = gpt5_opts.get("cache_control_ttl_seconds")

                input_messages = []
                for msg in messages:
                    role = msg.get("role", "user")
                    text = msg.get("content", "")
                    # ロールに応じて Responses API の item type を選択
                    item_type = "output_text" if role == "assistant" else "input_text"
                    content_item = {"type": item_type, "text": text}
                    # cache_control は“入力”のみに付与
                    if item_type == "input_text" and cache_type and cache_type != "none":
                        cache_control = {"type": cache_type}
                        if cache_ttl:
                            cache_control["ttl"] = cache_ttl
                        content_item["cache_control"] = cache_control
                    input_messages.append({"role": role, "content": [content_item]})

                response_kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "input": input_messages
                }

                sanitized_kwargs = dict(kwargs)
                # top_p, presence_penalty, frequency_penalty は Responses API 非対応
                for deprecated in ("top_p", "presence_penalty", "frequency_penalty"):
                    sanitized_kwargs.pop(deprecated, None)

                # temperature: Responses API でもモデルによっては対応 (e.g. gpt-5.2)
                temperature = sanitized_kwargs.pop("temperature", self.config.get("temperature"))
                if temperature is not None:
                    response_kwargs["temperature"] = temperature

                reasoning_cfg: Dict[str, Any] = {}
                reasoning_effort = sanitized_kwargs.pop("reasoning_effort", gpt5_opts.get("reasoning_effort"))
                if reasoning_effort:
                    reasoning_cfg["effort"] = reasoning_effort
                reasoning_summary = sanitized_kwargs.pop("reasoning_summary", gpt5_opts.get("reasoning_summary"))
                if reasoning_summary:
                    reasoning_cfg["summary"] = reasoning_summary
                if reasoning_cfg:
                    response_kwargs["reasoning"] = reasoning_cfg

                text_cfg: Dict[str, Any] = {}
                verbosity = sanitized_kwargs.pop("verbosity", gpt5_opts.get("verbosity"))
                if not verbosity:
                    legacy_verbosity = sanitized_kwargs.pop("text_verbosity", gpt5_opts.get("text_verbosity"))
                    verbosity = legacy_verbosity
                if verbosity:
                    text_cfg["verbosity"] = verbosity

                response_format = sanitized_kwargs.pop("response_format", gpt5_opts.get("response_format"))
                if response_format:
                    if isinstance(response_format, dict):
                        text_cfg["format"] = response_format
                    elif response_format != "text":
                        text_cfg["format"] = {"type": str(response_format)}

                if text_cfg:
                    response_kwargs["text"] = text_cfg

                max_output_tokens = sanitized_kwargs.pop(
                    "max_tokens",
                    gpt5_opts.get("max_output_tokens") or self.config.get("max_tokens", 4096)
                )
                if max_output_tokens:
                    response_kwargs["max_output_tokens"] = max_output_tokens

                metadata_value = sanitized_kwargs.pop("metadata", gpt5_opts.get("metadata"))
                if isinstance(metadata_value, dict) and metadata_value:
                    response_kwargs["metadata"] = metadata_value
                elif metadata_value is None:
                    sanitized_kwargs.pop("metadata", None)

                store_value = sanitized_kwargs.pop("store", gpt5_opts.get("store"))
                if store_value is not None:
                    response_kwargs["store"] = store_value

                include_value = sanitized_kwargs.pop("include", gpt5_opts.get("include"))
                if include_value is not None:
                    response_kwargs["include"] = include_value

                background_value = sanitized_kwargs.pop("background", gpt5_opts.get("background"))
                if background_value is not None:
                    response_kwargs["background"] = background_value

                parallel_tool_calls = sanitized_kwargs.pop("parallel_tool_calls", gpt5_opts.get("parallel_tool_calls"))
                if parallel_tool_calls is not None:
                    response_kwargs["parallel_tool_calls"] = parallel_tool_calls

                service_tier = sanitized_kwargs.pop("service_tier", gpt5_opts.get("service_tier"))
                if service_tier:
                    response_kwargs["service_tier"] = service_tier

                tool_choice = sanitized_kwargs.pop("tool_choice", gpt5_opts.get("tool_choice"))
                if tool_choice:
                    response_kwargs["tool_choice"] = tool_choice

                tools_value = sanitized_kwargs.pop("tools", gpt5_opts.get("tools"))
                if tools_value:
                    response_kwargs["tools"] = tools_value

                truncation = sanitized_kwargs.pop("truncation", gpt5_opts.get("truncation"))
                if truncation:
                    response_kwargs["truncation"] = truncation

                user_value = sanitized_kwargs.pop("user", gpt5_opts.get("user"))
                if user_value:
                    response_kwargs["user"] = user_value

                extra = gpt5_opts.get("extra")
                if isinstance(extra, dict):
                    for key, value in extra.items():
                        if value is not None and key not in response_kwargs:
                            response_kwargs[key] = value

                for key, value in sanitized_kwargs.items():
                    if value is not None:
                        response_kwargs[key] = value

                response = self.client.responses.create(**response_kwargs)
                text_output = getattr(response, "output_text", None)
                if text_output:
                    return text_output
                # フォールバック: content配列からテキストを抽出
                try:
                    outputs = []
                    for item in getattr(response, "output", []):
                        for content in getattr(item, "content", []):
                            if getattr(content, "type", "") == "output_text":
                                outputs.append(getattr(content, "text", ""))
                            elif hasattr(content, "text"):
                                outputs.append(content.text)
                    if outputs:
                        return "\n".join(outputs)
                except Exception:
                    pass
                return ""

            request_kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.get("temperature", 0.0)),
                "max_completion_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
                "timeout": self.config.get("timeout", 60)
            }

            # 呼び出し元のkwargsで上書き可能にする
            for key, value in kwargs.items():
                if key not in ("temperature", "max_tokens"):
                    request_kwargs[key] = value

            response = self.client.chat.completions.create(**request_kwargs)
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def get_effective_params(self) -> Dict[str, Any]:
        model_name = self.config.get("model", "gpt-4o-mini")
        if model_name.startswith("gpt-5"):
            gpt5_opts = self.config.get("gpt5_options", {})
            params: Dict[str, Any] = {
                "API": "Responses API",
                "model": model_name,
                "temperature": self.config.get("temperature"),
                "max_output_tokens": gpt5_opts.get("max_output_tokens") or self.config.get("max_tokens", 4096),
                "timeout": self.config.get("timeout", 60),
            }
            reasoning_effort = gpt5_opts.get("reasoning_effort")
            if reasoning_effort:
                params["reasoning.effort"] = reasoning_effort
            reasoning_summary = gpt5_opts.get("reasoning_summary")
            if reasoning_summary:
                params["reasoning.summary"] = reasoning_summary
            verbosity = gpt5_opts.get("verbosity") or gpt5_opts.get("text_verbosity")
            if verbosity:
                params["text.verbosity"] = verbosity
            response_format = gpt5_opts.get("response_format")
            if response_format:
                params["text.format"] = response_format
            return params
        else:
            return {
                "API": "Chat Completions API",
                "model": model_name,
                "temperature": self.config.get("temperature", 0.0),
                "max_completion_tokens": self.config.get("max_tokens", 4096),
                "timeout": self.config.get("timeout", 60),
            }

    def validate_connection(self) -> bool:
        """API接続を検証"""
        try:
            self.client.models.list()
            return True
        except Exception as e:
            import openai
            if isinstance(e, openai.AuthenticationError):
                raise Exception(f"認証エラー: APIキーが無効です - {str(e)}")
            elif isinstance(e, openai.RateLimitError):
                raise Exception(f"レート制限: API利用制限に達しています - {str(e)}")
            elif isinstance(e, openai.APIConnectionError):
                raise Exception(f"接続エラー: APIに接続できません - {str(e)}")
            else:
                raise Exception(f"OpenAI API エラー: {type(e).__name__} - {str(e)}")


class ClaudeClient(BaseLLMClient):
    """Claude (Anthropic) API クライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import anthropic
        self.client = anthropic.Anthropic(
            api_key=config.get("api_key"),
            base_url=config.get("base_url")
        )
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Claude APIでチャット補完を実行"""
        try:
            claude_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    if claude_messages and claude_messages[0]["role"] == "user":
                        claude_messages[0]["content"] = msg["content"] + "\n\n" + claude_messages[0]["content"]
                    else:
                        claude_messages.insert(0, {"role": "user", "content": msg["content"]})
                else:
                    claude_messages.append(msg)
            
            response = self.client.messages.create(
                model=self.config.get("model", "claude-3-opus-20240229"),
                messages=claude_messages,
                temperature=kwargs.get("temperature", self.config.get("temperature", 0.0)),
                max_tokens=kwargs.get("max_tokens", self.config.get("max_tokens", 4096))
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Claude API error: {str(e)}")
    
    def get_effective_params(self) -> Dict[str, Any]:
        return {
            "API": "Anthropic Messages API",
            "model": self.config.get("model", "claude-3-opus-20240229"),
            "temperature": self.config.get("temperature", 0.0),
            "max_tokens": self.config.get("max_tokens", 4096),
        }

    def validate_connection(self) -> bool:
        """API接続を検証"""
        try:
            self.chat_completion([{"role": "user", "content": "Hi"}])
            return True
        except Exception as e:
            import anthropic
            if hasattr(anthropic, 'AuthenticationError') and isinstance(e, anthropic.AuthenticationError):
                raise Exception(f"認証エラー: APIキーが無効です - {str(e)}")
            elif hasattr(anthropic, 'RateLimitError') and isinstance(e, anthropic.RateLimitError):
                raise Exception(f"レート制限: API利用制限に達しています - {str(e)}")
            elif "connection" in str(e).lower():
                raise Exception(f"接続エラー: Claude APIに接続できません - {str(e)}")
            else:
                raise Exception(f"Claude API エラー: {type(e).__name__} - {str(e)}")


class DeepSeekClient(BaseLLMClient):
    """DeepSeek API クライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import openai
        self.client = openai.OpenAI(
            api_key=config.get("api_key"),
            base_url=config.get("base_url", "https://api.deepseek.com")
        )
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """DeepSeek APIでチャット補完を実行"""
        try:
            response = self.client.chat.completions.create(
                model=self.config.get("model", "deepseek-chat"),
                messages=messages,
                temperature=kwargs.get("temperature", self.config.get("temperature", 0.0)),
                max_tokens=kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
                timeout=self.config.get("timeout", 60)
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"DeepSeek API error: {str(e)}")
    
    def validate_connection(self) -> bool:
        """API接続を検証"""
        try:
            self.client.models.list()
            return True
        except Exception as e:
            import openai
            if hasattr(openai, 'AuthenticationError') and isinstance(e, openai.AuthenticationError):
                raise Exception(f"認証エラー: APIキーが無効です - {str(e)}")
            elif hasattr(openai, 'RateLimitError') and isinstance(e, openai.RateLimitError):
                raise Exception(f"レート制限: API利用制限に達しています - {str(e)}")
            elif hasattr(openai, 'APIConnectionError') and isinstance(e, openai.APIConnectionError):
                raise Exception(f"接続エラー: DeepSeek APIに接続できません - {str(e)}")
            else:
                raise Exception(f"DeepSeek API エラー: {type(e).__name__} - {str(e)}")


class OpenRouterClient(BaseLLMClient):
    """OpenRouter API クライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import openai
        
        default_headers = {
            "HTTP-Referer": config.get("site_url", ""),
            "X-Title": config.get("site_name", "")
        }
        
        self.client = openai.OpenAI(
            api_key=config.get("api_key"),
            base_url=config.get("base_url", "https://openrouter.ai/api/v1"),
            default_headers=default_headers
        )
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """OpenRouter APIでチャット補完を実行"""
        try:
            request_kwargs = {
                "model": self.config.get("model", "openrouter/horizon-beta"),
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.get("temperature", 0.0)),
                "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
                "timeout": self.config.get("timeout", 60),
            }

            reasoning_effort = kwargs.get("reasoning_effort", self.config.get("reasoning_effort"))
            if reasoning_effort:
                request_kwargs["extra_body"] = {
                    "reasoning": {
                        "effort": reasoning_effort
                    }
                }

            response = self.client.chat.completions.create(**request_kwargs)
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenRouter API error: {str(e)}")

    def get_effective_params(self) -> Dict[str, Any]:
        params = {
            "API": "OpenRouter Chat Completions API",
            "model": self.config.get("model", "openrouter/horizon-beta"),
            "temperature": self.config.get("temperature", 0.0),
            "max_tokens": self.config.get("max_tokens", 4096),
            "timeout": self.config.get("timeout", 60),
        }
        reasoning_effort = self.config.get("reasoning_effort")
        if reasoning_effort:
            params["extra_body.reasoning.effort"] = reasoning_effort
        return params
    
    def validate_connection(self) -> bool:
        """API接続を検証"""
        try:
            self.chat_completion([{"role": "user", "content": "Hello"}])
            return True
        except Exception as e:
            import openai
            if hasattr(openai, 'AuthenticationError') and isinstance(e, openai.AuthenticationError):
                raise Exception(f"認証エラー: APIキーが無効です - {str(e)}")
            elif hasattr(openai, 'RateLimitError') and isinstance(e, openai.RateLimitError):
                raise Exception(f"レート制限: API利用制限に達しています - {str(e)}")
            elif hasattr(openai, 'APIConnectionError') and isinstance(e, openai.APIConnectionError):
                raise Exception(f"接続エラー: OpenRouter APIに接続できません - {str(e)}")
            else:
                raise Exception(f"OpenRouter API エラー: {type(e).__name__} - {str(e)}")


class GeminiClient(BaseLLMClient):
    """Google Gemini API クライアント (新SDK: google-genai)

    Gemini 2.5系: thinking_budget (整数トークン数) で思考量を制御
    Gemini 3系:   thinking_level (minimal/low/medium/high) で思考量を制御
    ※ 同一リクエストで両方を指定すると 400 エラーになる
    """

    # Gemini 2.5用: thinking_budget の推奨マッピング
    THINKING_BUDGET_MAP = {
        "off": 0,
        "low": 1024,
        "medium": 8192,
        "high": 24576,
        "dynamic": -1,
    }

    # Gemini 3用: thinking_level の有効値 (reasoning_effort互換)
    VALID_THINKING_LEVELS = {"minimal", "low", "medium", "high"}

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            from google import genai
            from google.genai import types
            self._genai = genai
            self._types = types
            self._client = genai.Client(api_key=config.get("api_key"))
            self._model_name = config.get("model", "gemini-2.5-flash")
        except ImportError:
            raise Exception(
                "google-genai パッケージがインストールされていません。"
                "'pip install google-genai' を実行してください。"
                "（旧 google-generativeai ではなく新SDKが必要です）"
            )

    def _is_gemini3(self) -> bool:
        """Gemini 3系モデルかどうか判定"""
        return "gemini-3" in self._model_name.lower()

    def _build_thinking_config(self, **kwargs):
        """モデルに応じた ThinkingConfig を構築

        Gemini 3系: thinking_level (文字列) を使用
        Gemini 2.5系: thinking_budget (整数) を使用
        ※ 同一リクエストで両方指定すると 400 エラー
        """
        types = self._types
        gemini_opts = self.config.get("gemini_options", {})

        if self._is_gemini3():
            thinking_level = kwargs.pop("thinking_level", gemini_opts.get("thinking_level", "low"))
            if isinstance(thinking_level, str):
                thinking_level = thinking_level.lower()
            if thinking_level not in self.VALID_THINKING_LEVELS:
                thinking_level = "low"
            return types.ThinkingConfig(thinking_level=thinking_level)
        else:
            thinking_budget = kwargs.pop("thinking_budget", gemini_opts.get("thinking_budget", -1))
            if isinstance(thinking_budget, str):
                thinking_budget = self.THINKING_BUDGET_MAP.get(thinking_budget.lower(), -1)
            return types.ThinkingConfig(thinking_budget=int(thinking_budget))

    def _build_generate_config(self, **kwargs):
        """gemini_options + kwargs から GenerateContentConfig を構築"""
        types = self._types
        gemini_opts = self.config.get("gemini_options", {})

        # thinking_config をモデルに応じて構築
        thinking_config = self._build_thinking_config(**kwargs)

        # safety_settings
        raw_safety = gemini_opts.get("safety_settings", [])
        safety_settings = []
        for s in raw_safety:
            safety_settings.append(types.SafetySetting(
                category=s["category"],
                threshold=s["threshold"],
            ))

        config_kwargs = {
            "temperature": kwargs.pop("temperature", self.config.get("temperature", 1.0)),
            "max_output_tokens": kwargs.pop("max_tokens", self.config.get("max_tokens", 8192)),
            "candidate_count": gemini_opts.get("candidate_count", 1),
            "safety_settings": safety_settings if safety_settings else None,
        }

        # response_mime_type
        response_mime_type = kwargs.pop(
            "response_mime_type",
            gemini_opts.get("response_mime_type")
        )
        if response_mime_type:
            config_kwargs["response_mime_type"] = response_mime_type

        if thinking_config is not None:
            config_kwargs["thinking_config"] = thinking_config

        return types.GenerateContentConfig(**config_kwargs)

    @staticmethod
    def _sanitize_json_response(text: str) -> str:
        """Gemini thinking併用時に発生する余分な括弧を除去して正しいJSONに修復する

        既知のパターン: 正常なJSON `{...}` の後に `\\n}` 等の余分な閉じ括弧が付く。
        修復は末尾が余分な括弧/空白のみの場合に限定し、それ以外はそのまま返す。
        """
        stripped = text.strip()
        if not stripped:
            return text
        # JSONらしい応答でなければそのまま返す
        if not (stripped.startswith("{") or stripped.startswith("[")):
            return text
        # まず正常にパースできるか試す
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            pass
        # raw_decode で最初の完全なJSONを取り出す
        decoder = json.JSONDecoder()
        try:
            _, end_idx = decoder.raw_decode(stripped)
            # 切り捨てる部分が余分な括弧・空白のみの場合だけ修復する
            remainder = stripped[end_idx:].strip()
            if remainder and all(c in "{}[] \t\n\r" for c in remainder):
                return stripped[:end_idx]
        except json.JSONDecodeError:
            pass
        return text

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Gemini APIでチャット補完を実行"""
        try:
            config = self._build_generate_config(**kwargs)

            # system と user/assistant メッセージを分離
            system_content = ""
            contents = []
            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                elif msg["role"] == "user":
                    contents.append(self._types.Content(
                        role="user",
                        parts=[self._types.Part(text=msg["content"])]
                    ))
                elif msg["role"] == "assistant":
                    contents.append(self._types.Content(
                        role="model",
                        parts=[self._types.Part(text=msg["content"])]
                    ))

            # system_instruction がある場合はconfigに設定
            if system_content:
                config.system_instruction = system_content

            if not contents:
                return ""

            response = self._client.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=config,
            )

            # レスポンスからテキストを抽出 (thinkingパーツを除外)
            raw_text = None
            if hasattr(response, "text") and response.text:
                raw_text = response.text
            else:
                # フォールバック: candidatesから手動抽出
                try:
                    parts = []
                    for candidate in getattr(response, "candidates", []):
                        for part in getattr(candidate.content, "parts", []):
                            if hasattr(part, "thought") and part.thought:
                                continue  # thinking パーツはスキップ
                            if hasattr(part, "text") and part.text:
                                parts.append(part.text)
                    if parts:
                        raw_text = "\n".join(parts)
                except Exception:
                    pass

            if not raw_text:
                return ""

            # thinking併用時の余分な括弧を修復
            return self._sanitize_json_response(raw_text)

        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    def get_effective_params(self) -> Dict[str, Any]:
        """実際にAPIに送信されるパラメータを返す"""
        gemini_opts = self.config.get("gemini_options", {})

        params: Dict[str, Any] = {
            "API": "Google GenAI SDK (google-genai)",
            "model": self._model_name,
            "temperature": self.config.get("temperature", 1.0),
            "max_output_tokens": self.config.get("max_tokens", 8192),
        }

        if self._is_gemini3():
            params["thinking_config.thinking_level"] = gemini_opts.get("thinking_level", "low")
        else:
            thinking_budget = gemini_opts.get("thinking_budget", -1)
            if isinstance(thinking_budget, str):
                thinking_budget = self.THINKING_BUDGET_MAP.get(thinking_budget.lower(), -1)
            label = next(
                (k for k, v in self.THINKING_BUDGET_MAP.items() if v == thinking_budget),
                None
            )
            display = f"{thinking_budget}"
            if label:
                display += f" ({label})"
            params["thinking_config.thinking_budget"] = display

        response_mime_type = gemini_opts.get("response_mime_type")
        if response_mime_type:
            params["response_mime_type"] = response_mime_type

        candidate_count = gemini_opts.get("candidate_count", 1)
        if candidate_count != 1:
            params["candidate_count"] = candidate_count

        safety_count = len(gemini_opts.get("safety_settings", []))
        if safety_count:
            params["safety_settings"] = f"{safety_count}件のルール"

        params["注意"] = "Gemini 3ではtemperature=1.0推奨（変更するとループ等の予期しない動作の可能性）"
        return params

    def validate_connection(self) -> bool:
        """API接続を検証"""
        try:
            config = self._types.GenerateContentConfig(
                max_output_tokens=32,
            )
            response = self._client.models.generate_content(
                model=self._model_name,
                contents="Hello",
                config=config,
            )
            return True
        except Exception as e:
            err_str = str(e)
            if "API key" in err_str or "API_KEY" in err_str or "PERMISSION_DENIED" in err_str:
                raise Exception(f"認証エラー: APIキーが無効です - {err_str}")
            elif "quota" in err_str.lower() or "RESOURCE_EXHAUSTED" in err_str:
                raise Exception(f"レート制限: API利用制限に達しています - {err_str}")
            else:
                raise Exception(f"Gemini API エラー: {type(e).__name__} - {err_str}")


class LocalLLMClient(BaseLLMClient):
    """ローカルLLM (vLLM/OpenAI互換API) クライアント"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:8000/v1")
        self.model = config.get("model", "llama3:8b")
        import openai
        api_key = config.get("api_key") or "EMPTY"
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=self.base_url
        )
    
    def _is_reasoning_model(self) -> bool:
        """gpt-ossなどreasoning_effortをサポートするモデルかどうか判定"""
        reasoning_models = ["gpt-oss"]
        return any(rm in self.model.lower() for rm in reasoning_models)

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """vLLM(OpenAI互換)でチャット補完を実行"""
        try:
            request_kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.get("temperature", 0.0)),
                "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
                "timeout": self.config.get("timeout", 120),
            }

            # local(vLLM)はデフォルトでJSON出力を要求（必要なら設定/引数で上書き可）
            response_format = kwargs.get("response_format", self.config.get("response_format"))
            if response_format is None:
                response_format = {"type": "json_object"}
            elif isinstance(response_format, str):
                response_format = {"type": response_format}
            if response_format:
                request_kwargs["response_format"] = response_format

            # gpt-ossなどの推論モデルの場合:
            #   - 公式推奨: temperature=1.0, top_p=1.0 (サンプリング制御はreasoning_effortで行う)
            #   - reasoning_effortをchat_template_kwargs経由で渡す
            if self._is_reasoning_model():
                request_kwargs["temperature"] = 1.0
                request_kwargs["top_p"] = 1.0
                reasoning_effort = kwargs.get("reasoning_effort", self.config.get("reasoning_effort"))
                if reasoning_effort:
                    extra_body = request_kwargs.get("extra_body", {})
                    chat_template_kwargs = extra_body.get("chat_template_kwargs", {})
                    chat_template_kwargs["reasoning_effort"] = reasoning_effort
                    extra_body["chat_template_kwargs"] = chat_template_kwargs
                    request_kwargs["extra_body"] = extra_body

            for key, value in kwargs.items():
                if key in {"temperature", "max_tokens", "response_format", "reasoning_effort"}:
                    continue
                if value is not None:
                    request_kwargs[key] = value

            response = self.client.chat.completions.create(**request_kwargs)
            message = response.choices[0].message
            # 推論モデルではcontentがNoneでreasoning_contentに出力される場合がある
            content = message.content
            if content is None and hasattr(message, "reasoning_content") and message.reasoning_content:
                content = message.reasoning_content
            return content or ""
        except Exception as e:
            raise Exception(f"Local LLM error: {str(e)}")
    
    def get_effective_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "API": "vLLM (OpenAI互換) Chat Completions API",
            "model": self.model,
            "timeout": self.config.get("timeout", 120),
        }
        if self._is_reasoning_model():
            # gpt-oss: 公式推奨値を強制
            params["temperature"] = "1.0 (公式推奨: 固定)"
            params["top_p"] = "1.0 (公式推奨: 固定)"
            params["max_tokens"] = self.config.get("max_tokens", 4096)
            reasoning_effort = self.config.get("reasoning_effort")
            if reasoning_effort:
                params["extra_body.chat_template_kwargs.reasoning_effort"] = reasoning_effort
            else:
                params["reasoning_effort"] = "(未指定 → chat_templateデフォルト: medium)"
        else:
            params["temperature"] = self.config.get("temperature", 0.0)
            params["max_tokens"] = self.config.get("max_tokens", 4096)
        # response_format
        response_format = self.config.get("response_format")
        if response_format is None:
            response_format = {"type": "json_object"}
        params["response_format"] = response_format
        return params

    def validate_connection(self) -> bool:
        """vLLM(OpenAI互換API)への接続を検証"""
        try:
            models = self.client.models.list()
            model_ids = [getattr(m, "id", "") for m in getattr(models, "data", [])]
            if self.model not in model_ids:
                available = ", ".join(model_ids) if model_ids else "なし"
                raise Exception(f"モデル '{self.model}' が見つかりません。利用可能なモデル: {available}")
            return True
        except Exception as e:
            if "モデル" in str(e):
                raise
            raise Exception(f"vLLM接続エラー: {type(e).__name__} - {str(e)}")


class OllamaClient(BaseLLMClient):
    """Ollama API クライアント"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "llama3:8b")

    def _is_reasoning_model(self) -> bool:
        """gpt-ossなどreasoning_effortをサポートするモデルかどうか判定"""
        reasoning_models = ["gpt-oss"]
        return any(rm in self.model.lower() for rm in reasoning_models)

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Ollamaでチャット補完を実行"""
        try:
            url = f"{self.base_url}/api/chat"

            # default_request から基本ペイロードを構築
            default_req = self.config.get("default_request", {})
            options = dict(default_req.get("options", {}))

            # kwargs / config からのオーバーライド
            if "temperature" in kwargs:
                options["temperature"] = kwargs["temperature"]
            elif "temperature" not in options:
                options["temperature"] = self.config.get("temperature", 0.0)

            if "max_tokens" in kwargs:
                options["num_predict"] = kwargs["max_tokens"]
            elif "num_predict" not in options:
                options["num_predict"] = self.config.get("max_tokens", 4096)

            payload = {
                "model": self.model,
                "messages": messages,
                "stream": default_req.get("stream", False),
                "options": options,
            }

            # default_request の追加フィールド（format, keep_alive 等）
            for key in ("format", "keep_alive"):
                if key in default_req:
                    payload[key] = default_req[key]

            # gpt-oss等の推論モデル: reasoning_effort を options 経由で渡す
            if self._is_reasoning_model():
                # 推論モデルは temperature=1.0, top_p=1.0 が推奨
                options["temperature"] = 1.0
                options["top_p"] = 1.0
                reasoning_effort = kwargs.get("reasoning_effort", self.config.get("reasoning_effort"))
                if reasoning_effort:
                    options["reasoning_effort"] = reasoning_effort

            response = requests.post(
                url,
                json=payload,
                timeout=self.config.get("timeout", 120)
            )
            response.raise_for_status()

            result = response.json()
            return result.get("message", {}).get("content", "")
        except Exception as e:
            raise Exception(f"Ollama error: {str(e)}")

    def get_effective_params(self) -> Dict[str, Any]:
        default_req = self.config.get("default_request", {})
        default_options = default_req.get("options", {})
        params: Dict[str, Any] = {
            "API": "Ollama /api/chat",
            "model": self.model,
            "timeout": self.config.get("timeout", 120),
            "stream": default_req.get("stream", False),
        }
        if self._is_reasoning_model():
            params["options.temperature"] = "1.0 (推論モデル推奨: 固定)"
            params["options.top_p"] = "1.0 (推論モデル推奨: 固定)"
            params["options.num_predict"] = default_options.get("num_predict", self.config.get("max_tokens", 4096))
            reasoning_effort = self.config.get("reasoning_effort")
            if reasoning_effort:
                params["options.reasoning_effort"] = reasoning_effort
            else:
                params["reasoning_effort"] = "(未指定 → デフォルト: medium)"
        else:
            params["options.temperature"] = default_options.get("temperature", self.config.get("temperature", 0.0))
            params["options.num_predict"] = default_options.get("num_predict", self.config.get("max_tokens", 4096))
        if "format" in default_req:
            params["format"] = default_req["format"]
        if "keep_alive" in default_req:
            params["keep_alive"] = default_req["keep_alive"]
        return params

    def validate_connection(self) -> bool:
        """Ollama接続を検証"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                if self.model not in model_names:
                    available = ", ".join(model_names) if model_names else "なし"
                    raise Exception(f"モデル '{self.model}' が見つかりません。利用可能なモデル: {available}")
                return True
            else:
                raise Exception(f"Ollamaサービスが応答しません (HTTP {response.status_code})")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Ollamaサービスに接続できません。'{self.base_url}' でサービスが起動しているか確認してください")
        except requests.exceptions.Timeout:
            raise Exception("Ollamaサービスへの接続がタイムアウトしました")
        except Exception as e:
            if "モデル" in str(e):
                raise
            raise Exception(f"Ollama接続エラー: {type(e).__name__} - {str(e)}")


class LLMClientFactory:
    """LLMクライアントのファクトリークラス"""
    
    @staticmethod
    def create_client(provider: str, config: Dict[str, Any]) -> BaseLLMClient:
        """指定されたプロバイダーのクライアントを作成"""
        if provider == LLMProvider.OPENAI.value:
            return OpenAIClient(config)
        elif provider == LLMProvider.CLAUDE.value:
            return ClaudeClient(config)
        elif provider == LLMProvider.DEEPSEEK.value:
            return DeepSeekClient(config)
        elif provider == LLMProvider.LOCAL.value:
            return LocalLLMClient(config)
        elif provider == LLMProvider.OLLAMA.value:
            return OllamaClient(config)
        elif provider == LLMProvider.OPENROUTER.value:
            return OpenRouterClient(config)
        elif provider == LLMProvider.GEMINI.value:  # 追加
            return GeminiClient(config)
        else:
            raise ValueError(f"Unsupported provider: {provider}")


class UnifiedLLMClient:
    """統一的なLLMクライアントインターフェース"""
    
    def __init__(self, config_path: Path = None):
        """
        Args:
            config_path: 設定ファイルのパス
        """
        self.config_manager = LLMConfig(config_path)
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """現在の設定に基づいてクライアントを初期化"""
        provider = self.config_manager.get_active_provider()
        config = self.config_manager.get_provider_config(provider)
        self._client = LLMClientFactory.create_client(provider, config)
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """チャット補完を実行（リトライ機能付き）"""
        retry_config = self.config_manager.get_retry_config()
        max_retries = retry_config.get("max_retries", 3)
        retry_delay = retry_config.get("retry_delay", 2)
        use_backoff = retry_config.get("exponential_backoff", True)
        
        import time
        
        for attempt in range(max_retries):
            try:
                return self._client.chat_completion(messages, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                wait_time = retry_delay * (2 ** attempt if use_backoff else 1)
                print(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {str(e)}")
                time.sleep(wait_time)
    
    def switch_provider(self, provider: str):
        """プロバイダーを切り替え"""
        self.config_manager.set_active_provider(provider)
        self._init_client()
    
    def validate_connection(self) -> bool:
        """現在のプロバイダーの接続を検証"""
        return self._client.validate_connection()
    
    def get_current_provider(self) -> str:
        """現在のプロバイダーを取得"""
        return self.config_manager.get_active_provider()
    
    def get_effective_params(self) -> Dict[str, Any]:
        """現在のクライアントが実際にAPIに送信するパラメータを取得"""
        return self._client.get_effective_params()

    def update_config(self, **kwargs):
        """現在のプロバイダーの設定を更新"""
        provider = self.get_current_provider()
        self.config_manager.update_provider_config(provider, **kwargs)
        self._init_client()


# 既存コードとの互換性のためのヘルパー関数
def init_llm_client(provider: str = None) -> UnifiedLLMClient:
    """
    LLMクライアントを初期化
    
    Args:
        provider: 使用するプロバイダー（None の場合は設定ファイルのデフォルト）
    
    Returns:
        UnifiedLLMClient インスタンス
    """
    client = UnifiedLLMClient()
    
    if provider:
        client.switch_provider(provider)
    
    return client


def ask_llm(prompt: str, provider: str = None, **kwargs) -> str:
    """
    シンプルなLLM問い合わせ関数（既存コードとの互換性用）
    
    Args:
        prompt: プロンプト文字列
        provider: 使用するプロバイダー
        **kwargs: その他のパラメータ
    
    Returns:
        LLMの応答文字列
    """
    client = init_llm_client(provider)
    messages = [{"role": "user", "content": prompt}]
    return client.chat_completion(messages, **kwargs)
