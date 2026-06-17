"""网页抓取工具"""

import json
import re
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import quote

from ...base import BaseTool, ToolExecResult


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "获取指定 URL 的网页内容"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要获取的 URL"},
                "timeout": {"type": "integer", "description": "请求超时秒数，默认 10", "default": 10},
            },
            "required": ["url"],
        }

    async def execute(self, url: str, timeout: int = 10) -> ToolExecResult:
        try:
            req = Request(url, headers={"User-Agent": "ConfigBot/1.0"})
            with urlopen(req, timeout=timeout) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                return ToolExecResult(
                    success=True,
                    data=content[:5000],
                    metadata={"status": resp.status, "url": url, "truncated": len(content) > 5000},
                )
        except URLError as e:
            return ToolExecResult(success=False, error=f"请求失败: {e.reason}")
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))


class HttpPostTool(BaseTool):
    """HTTP POST 请求工具"""
    name = "http_post"
    description = "发送 HTTP POST 请求"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "请求 URL"},
                "body": {"type": "string", "description": "请求体内容"},
                "content_type": {"type": "string", "description": "Content-Type", "default": "application/json"},
            },
            "required": ["url", "body"],
        }

    async def execute(self, url: str, body: str, content_type: str = "application/json") -> ToolExecResult:
        try:
            data = body.encode("utf-8")
            req = Request(
                url,
                data=data,
                headers={"User-Agent": "ConfigBot/1.0", "Content-Type": content_type},
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                return ToolExecResult(
                    success=True,
                    data=content[:5000],
                    metadata={"status": resp.status, "url": url},
                )
        except Exception as e:
            return ToolExecResult(success=False, error=str(e))


class BaiduWeatherTool(BaseTool):
    """通过百度搜索查询指定城市天气"""
    name = "baidu_weather"
    description = "访问百度首页查询指定城市的天气信息"

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如 北京、上海、深圳",
                },
            },
            "required": ["city"],
        }

    async def execute(self, city: str) -> ToolExecResult:
        try:
            # 方案1: 尝试百度天气 API
            result = await self._try_baidu_api(city)
            if result:
                return result

            # 方案2: 尝试百度搜索页面
            result = await self._try_baidu_search(city)
            if result:
                return result

            # 方案3: 备用天气服务
            return await self._fallback_weather(city)

        except Exception as e:
            return ToolExecResult(success=False, error=str(e))

    async def _try_baidu_api(self, city: str) -> Optional[ToolExecResult]:
        """尝试百度天气 API 接口"""
        try:
            query = quote(city)
            url = (
                f"https://weathernew.pae.baidu.com/weathernew/"
                f"pc?query={query}&srcid=4982"
            )
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.baidu.com/",
            })
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("status") == 0 and data.get("data"):
                return self._parse_baidu_api(data["data"], city)
        except Exception:
            pass
        return None

    def _parse_baidu_api(self, data: dict, city: str) -> ToolExecResult:
        """解析百度天气 API 返回数据"""
        wd = data.get("weather") or data.get("weatherData") or {}
        forecast_raw = wd.get("forecast") or wd.get("weather") or []

        weather_info = {
            "city": city,
            "source": "百度天气",
            "temperature": None,
            "weather_desc": None,
            "wind": None,
            "humidity": None,
            "update_time": None,
            "forecast": [],
        }

        if forecast_raw:
            today = forecast_raw[0] if isinstance(forecast_raw, list) else forecast_raw
            weather_info["temperature"] = f"{today.get('low', '?')} ~ {today.get('high', '?')}"
            weather_info["weather_desc"] = today.get("type") or today.get("text")
            weather_info["wind"] = today.get("fengli") or today.get("fl")
            weather_info["humidity"] = today.get("humidity") or today.get("shidu")

            for day in forecast_raw[:7]:
                weather_info["forecast"].append({
                    "day": day.get("date", ""),
                    "temp": f"{day.get('low', '?')} ~ {day.get('high', '?')}",
                    "desc": day.get("type", ""),
                })

        return ToolExecResult(
            success=True,
            data=weather_info,
            metadata={"city": city, "source": "百度天气API"},
        )

    async def _try_baidu_search(self, city: str) -> Optional[ToolExecResult]:
        """尝试百度搜索页面抓取"""
        try:
            query = quote(f"{city} 天气")
            url = f"https://www.baidu.com/s?wd={query}"

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Cache-Control": "max-age=0",
                "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }

            req = Request(url, headers=headers)
            with urlopen(req, timeout=15) as resp:
                raw = resp.read()

            html = self._decode_response(raw, resp.headers)

            if self._is_blocked(html):
                return None

            weather = self._parse_weather(html, city)
            return ToolExecResult(
                success=True,
                data=weather,
                metadata={"city": city, "url": url, "status": resp.status},
            )
        except Exception:
            return None

    def _decode_response(self, raw: bytes, headers) -> str:
        """处理响应解码，支持 gzip/deflate"""
        import gzip
        import zlib

        content_encoding = headers.get("Content-Encoding", "").lower()
        try:
            if "gzip" in content_encoding:
                raw = gzip.decompress(raw)
            elif "deflate" in content_encoding:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        except Exception:
            pass
        return raw.decode("utf-8", errors="replace")

    def _is_blocked(self, html: str) -> bool:
        """检测是否被反爬拦截"""
        blocked_keywords = ["百度安全验证", "网络不给力", "时间超时"]
        return len(html) < 3000 and any(kw in html for kw in blocked_keywords)

    async def _fallback_weather(self, city: str) -> ToolExecResult:
        """使用 wttr.in 获取天气作为备用方案"""
        try:
            query = quote(city)
            url = f"https://wttr.in/{query}?format=j1"
            req = Request(url, headers={"User-Agent": "curl/8.0"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            current = data.get("current_condition", [{}])[0]
            weather_info = {
                "city": city,
                "source": "wttr.in",
                "temperature": current.get("temp_C") and f"{current['temp_C']}°C",
                "weather_desc": current.get("weatherDesc", [{}])[0].get("value"),
                "wind": current.get("windspeedKmph") and f"{current['windspeedKmph']}km/h",
                "humidity": current.get("humidity") and f"{current['humidity']}%",
                "update_time": current.get("observation_time"),
                "forecast": [],
            }

            for day in data.get("weather", [])[:3]:
                weather_info["forecast"].append({
                    "day": day.get("date", ""),
                    "temp": f"{day.get('mintempC', '?')}°C ~ {day.get('maxtempC', '?')}°C",
                    "desc": day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", ""),
                })

            return ToolExecResult(
                success=True,
                data=weather_info,
                metadata={"city": city, "source": "wttr.in", "note": "百度请求被拦截，使用备用天气服务"},
            )
        except Exception as e:
            return ToolExecResult(success=False, error=f"备用天气服务也失败: {e}")

    def _parse_weather(self, html: str, city: str) -> Dict[str, Any]:
        """从百度搜索结果页面解析天气信息"""
        result = {
            "city": city,
            "source": "百度搜索",
            "temperature": None,
            "weather_desc": None,
            "wind": None,
            "humidity": None,
            "update_time": None,
            "forecast": [],
        }

        # 方案1: 尝试从页面内嵌 JSON 数据中提取
        json_data = self._extract_json_weather(html)
        if json_data:
            self._fill_from_json(result, json_data)

        # 方案2: 正则表达式兜底提取
        if not result["temperature"]:
            self._fill_by_regex(result, html)

        # 如果什么都没解析到，返回原始文本摘要
        if not any([result["temperature"], result["weather_desc"], result["forecast"]]):
            snippet = re.sub(r"<[^>]+>", "", html)
            snippet = re.sub(r"\s+", " ", snippet)
            result["raw_snippet"] = snippet[:500]

        return result

    def _extract_json_weather(self, html: str) -> dict:
        """从页面中提取天气相关的 JSON 数据块"""
        # 匹配百度天气卡片中的天气数据 JSON
        # 百度页面结构: <script> 中含有 weatherData 或 weather_content
        patterns = [
            r'"weatherData"\s*:\s*(\{.+?\})\s*,\s*"currentCity',
            r'"weather_content"\s*:\s*(\{.+?\})\s*,\s*"',
            r'"today"\s*:\s*(\{[^}]+?\})\s*[,;]',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

        # 尝试提取整个 script 中的 JSON 大对象
        script_match = re.search(
            r'<script[^>]*>\s*(?:window\.\w+\s*=\s*)?(\{[^<]*?"weatherData"[^<]*?\})\s*;?\s*</script>',
            html, re.DOTALL,
        )
        if script_match:
            try:
                return json.loads(script_match.group(1))
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return {}

    def _fill_from_json(self, result: dict, data: dict) -> None:
        """从 JSON 数据填充天气信息"""
        # 提取 weatherData
        wd = data.get("weatherData") or data.get("weather_content") or {}

        # 当前天气位于 weatherData 中
        today = wd.get("today") or {}
        if isinstance(today, dict):
            if not result["temperature"]:
                temp = today.get("temperature") or today.get("temp") or today.get("wendu")
                if temp:
                    result["temperature"] = str(temp) if "°" in str(temp) else f"{temp}°C"
            if not result["weather_desc"]:
                desc = today.get("weather") or today.get("type") or today.get("text")
                if desc:
                    result["weather_desc"] = desc
            if not result["wind"]:
                wind = today.get("wind") or today.get("fengli") or today.get("fl")
                if wind:
                    result["wind"] = str(wind)
            if not result["humidity"]:
                hum = today.get("humidity") or today.get("shidu")
                if hum:
                    result["humidity"] = str(hum) if "%" in str(hum) else f"{hum}%"

        # 预报数据
        forecast = wd.get("forecast") or wd.get("weather") or {}
        if isinstance(forecast, dict):
            days = forecast.get("day") or forecast.get("list") or forecast.get("data") or []
            if isinstance(days, list):
                for day in days[:7]:
                    if isinstance(day, dict):
                        result["forecast"].append({
                            "day": day.get("date") or day.get("day") or day.get("ri") or "",
                            "temp": day.get("temperature") or day.get("temp") or day.get("wendu") or "",
                            "desc": day.get("weather") or day.get("type") or day.get("text") or "",
                        })

        # 更新时间
        if not result["update_time"]:
            result["update_time"] = wd.get("updateTime") or wd.get("time") or wd.get("pubdate")

    def _fill_by_regex(self, result: dict, html: str) -> None:
        """通过正则表达式提取天气信息（兜底方案）"""
        # 温度：匹配合理范围 -50~50°C 的温度值
        # 优先匹配带范围的 如 "19°C ~ 30°C"
        temp_match = re.search(
            r'(?:气温|温度|temp)[^<]{0,20}?(-?\d{1,2})\s*[°℃]\s*[~～]\s*(-?\d{1,2})\s*[°℃]',
            html, re.IGNORECASE,
        )
        if not temp_match:
            # 匹配独立温度值，限制在合理范围 (-50 ~ 50)
            temp_match = re.search(
                r'(?:气温|温度|temp)[^<]{0,20}?(-?\d{1,2})\s*[°℃]',
                html, re.IGNORECASE,
            )
        if temp_match:
            if temp_match.lastindex and temp_match.lastindex >= 2 and temp_match.group(2):
                result["temperature"] = f"{temp_match.group(1)}°C ~ {temp_match.group(2)}°C"
            else:
                result["temperature"] = f"{temp_match.group(1)}°C"

        # 天气描述：匹配常见天气词汇
        weather_words = r'(晴|多云|阴|小雨|中雨|大雨|暴雨|雷阵雨|阵雨|小雪|中雪|大雪|雾|霾|沙尘暴|阴转晴|多云转晴)'
        desc_match = re.search(
            r'(?:天气|weather)[^<]{0,30}?' + weather_words,
            html, re.IGNORECASE,
        )
        if not desc_match:
            desc_match = re.search(weather_words, html)
        if desc_match:
            result["weather_desc"] = desc_match.group(1)

        # 风力
        wind_match = re.search(r'(?:风力|风)[：:]\s*([^<\n]{1,10})', html)
        if not wind_match:
            wind_match = re.search(r'(\d+级[^<\n]{0,5})', html)
        if wind_match:
            w = wind_match.group(1).strip()
            if len(w) <= 10:
                result["wind"] = w

        # 湿度
        hum_match = re.search(r'(?:湿度)[：:]\s*(\d{1,3}[%％])', html)
        if hum_match:
            result["humidity"] = hum_match.group(1)

        # 更新时间
        update_match = re.search(r'(?:更新|发布)[于时间]?[：:]\s*([^<\n]{5,30})', html)
        if update_match:
            result["update_time"] = update_match.group(1).strip()

        # 逐日预报
        day_pattern = re.compile(
            r'(\d{1,2}日|今天|明天|后天|周[一二三四五六日])'
            r'[^<]{0,30}?'
            r'(-?\d{1,2})\s*[°℃]?\s*[~～]\s*(-?\d{1,2})\s*[°℃]?',
            re.DOTALL,
        )
        seen = set()
        for m in day_pattern.finditer(html):
            key = (m.group(1), m.group(2), m.group(3))
            if key not in seen:
                seen.add(key)
                result["forecast"].append({
                    "day": m.group(1),
                    "temp": f"{m.group(2)}°C ~ {m.group(3)}°C",
                })
            if len(result["forecast"]) >= 7:
                break