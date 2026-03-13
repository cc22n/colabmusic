"""
API views for the audio app.

waveform_data:          GET /api/waveform/<model_name>/<object_id>/
                        Returns pre-computed waveform peaks as JSON.

processing_status_poll: GET /api/audio/status/<model_name>/<object_id>/
                        HTMX polling — returns an HTML status badge partial.
"""

import logging

from django.apps import apps
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .utils import get_streaming_url

logger = logging.getLogger(__name__)

# Maps URL slug to (app_label, model_class_name)
AUDIO_MODEL_MAP = {
    "beat": ("projects", "Beat"),
    "vocaltrack": ("projects", "VocalTrack"),
    "finalmix": ("projects", "FinalMix"),
}


def _get_audio_object(model_name: str, object_id: int):
    """Return the model instance or None if model_name is unknown."""
    config = AUDIO_MODEL_MAP.get(model_name.lower())
    if config is None:
        return None
    app_label, class_name = config
    Model = apps.get_model(app_label, class_name)
    return get_object_or_404(Model, pk=object_id)


# ---------------------------------------------------------------------------
# GET /api/waveform/<model_name>/<object_id>/
# ---------------------------------------------------------------------------


@require_GET
def waveform_data(request, model_name: str, object_id: int):
    """
    Return the pre-computed waveform peaks for a Beat, VocalTrack or FinalMix.
    Response: {"peaks": [...], "streaming_url": "...", "duration": 183.5}
    Returns 202 if still processing, 400 for unknown model.
    """
    obj = _get_audio_object(model_name, object_id)
    if obj is None:
        return JsonResponse({"error": "Modelo no soportado"}, status=400)

    if obj.processing_status != "ready":
        return JsonResponse(
            {
                "status": obj.processing_status,
                "message": "Audio en proceso. Intenta de nuevo pronto.",
            },
            status=202,
        )

    peaks = []
    if obj.waveform_data:
        peaks = obj.waveform_data.get("peaks", [])

    # Streaming URL: presigned S3 in production, local media URL in debug
    streaming_url = None
    if obj.streaming_file and obj.streaming_file.name:
        streaming_url = get_streaming_url(obj.streaming_file, request)
    elif obj.original_file and obj.original_file.name:
        streaming_url = get_streaming_url(obj.original_file, request)

    duration = None
    if obj.audio_duration:
        duration = obj.audio_duration.total_seconds()

    return JsonResponse(
        {
            "peaks": peaks,
            "streaming_url": streaming_url,
            "duration": duration,
            "status": "ready",
        }
    )


# ---------------------------------------------------------------------------
# GET /api/audio/status/<model_name>/<object_id>/
# ---------------------------------------------------------------------------


@require_GET
def processing_status_poll(request, model_name: str, object_id: int):
    """
    HTMX polling endpoint.
    Returns an HTML snippet that replaces itself via hx-swap="outerHTML".
    When status == 'ready', returns the full Wavesurfer.js player so polling stops.
    """
    obj = _get_audio_object(model_name, object_id)
    if obj is None:
        return HttpResponse(
            '<span class="text-red-400 text-xs">Error: modelo no soportado</span>',
            status=400,
        )

    status = obj.processing_status

    if status == "ready":
        streaming_url = None
        if obj.streaming_file and obj.streaming_file.name:
            streaming_url = get_streaming_url(obj.streaming_file, request)
        elif obj.original_file and obj.original_file.name:
            streaming_url = get_streaming_url(obj.original_file, request)

        track_id = f"{model_name}-{object_id}"
        html = _render_player_html(track_id, object_id, model_name, streaming_url)
        return HttpResponse(html)

    if status == "failed":
        html = (
            '<span class="text-xs text-red-400">'
            "⚠ Error al procesar el audio."
            "</span>"
        )
        return HttpResponse(html)

    # Still pending / processing — keep polling every 3 seconds
    poll_url = f"/api/audio/status/{model_name}/{object_id}/"
    label = "En cola..." if status == "pending" else "Procesando audio..."
    html = (
        f'<div hx-get="{poll_url}" hx-trigger="every 3s" hx-swap="outerHTML" '
        f'class="text-xs text-yellow-400 animate-pulse mt-2">{label}</div>'
    )
    return HttpResponse(html)


def _render_player_html(
    track_id: str, object_id: int, model_name: str, streaming_url
) -> str:
    """Return the Wavesurfer.js player HTML for a ready audio object."""
    waveform_url = f"/api/waveform/{model_name}/{object_id}/"
    audio_src = streaming_url or ""

    return (
        f'<div class="mt-3 audio-player" id="player-{track_id}">'
        f'  <div id="waveform-{track_id}"'
        f'       class="rounded overflow-hidden bg-gray-900 border border-gray-700"'
        f'       style="height:60px;"></div>'
        f'  <div class="flex items-center gap-3 mt-2">'
        f'    <button'
        f'      onclick="window._wsPlayers&&window._wsPlayers[\'{track_id}\']&&window._wsPlayers[\'{track_id}\'].playPause()"'
        f'      class="w-8 h-8 flex items-center justify-center rounded-full bg-purple-600 hover:bg-purple-500 text-white text-xs transition-colors"'
        f'      title="Reproducir / Pausar">&#9654;</button>'
        f'    <span id="time-{track_id}" class="text-xs text-gray-400 tabular-nums">0:00 / 0:00</span>'
        f'  </div>'
        f'</div>'
        f"<script>"
        f"(function(){{"
        f"  if(!window.WaveSurfer)return;"
        f"  window._wsPlayers=window._wsPlayers||{{}};"
        f"  fetch('{waveform_url}')"
        f"    .then(function(r){{return r.json();}})"
        f"    .then(function(data){{"
        f"      var url=data.streaming_url||'{audio_src}';"
        f"      if(!url)return;"
        f"      var ws=WaveSurfer.create({{"
        f"        container:'#waveform-{track_id}',"
        f"        waveColor:'#7C3AED',progressColor:'#4C1D95',"
        f"        cursorColor:'#A78BFA',barWidth:2,barRadius:2,"
        f"        height:60,normalize:true,backend:'MediaElement'"
        f"      }});"
        f"      ws.load(url,data.peaks||[]);"
        f"      window._wsPlayers['{track_id}']=ws;"
        f"      ws.on('audioprocess',function(){{"
        f"        var el=document.getElementById('time-{track_id}');"
        f"        if(!el)return;"
        f"        el.textContent=_fmt(ws.getCurrentTime())+' / '+_fmt(ws.getDuration());"
        f"      }});"
        f"      function _fmt(s){{var m=Math.floor(s/60),sec=Math.floor(s%60);return m+':'+(sec<10?'0':'')+sec;}}"
        f"    }})"
        f"    .catch(function(e){{console.warn('WaveSurfer load',e);}});"
        f"}})();"
        f"</script>"
    )
