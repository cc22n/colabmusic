from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.models import Genre

from .forms import BeatSubmitForm, LyricsForm, ProjectForm, VocalSubmitForm
from .models import (
    Beat,
    FinalMix,
    Lyrics,
    Project,
    ProjectStatus,
    ProjectType,
    VocalTrack,
)


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


# ── Browse / List ──────────────────────────────────────────────────────────────


class ProjectListView(ListView):
    model = Project
    template_name = "projects/list.html"
    context_object_name = "projects"
    paginate_by = 12

    def get_queryset(self):
        qs = (
            Project.objects.filter(is_public=True)
            .exclude(status=ProjectStatus.ARCHIVED)
            .select_related("genre", "created_by")
            .prefetch_related("tags")
            .order_by("-created_at")
        )
        status = self.request.GET.get("status")
        genre = self.request.GET.get("genre")
        project_type = self.request.GET.get("type")
        q = self.request.GET.get("q", "").strip()

        if status:
            qs = qs.filter(status=status)
        if genre:
            qs = qs.filter(genre__slug=genre)
        if project_type:
            qs = qs.filter(project_type=project_type)
        if q:
            qs = qs.filter(title__icontains=q)
        return qs

    def get_template_names(self):
        if _is_htmx(self.request):
            return ["projects/partials/project_list.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["genres"] = Genre.objects.all()
        ctx["status_choices"] = ProjectStatus.choices
        ctx["type_choices"] = ProjectType.choices
        ctx["current_filters"] = {
            "status": self.request.GET.get("status", ""),
            "genre": self.request.GET.get("genre", ""),
            "type": self.request.GET.get("type", ""),
            "q": self.request.GET.get("q", ""),
        }
        return ctx


# ── Detail ─────────────────────────────────────────────────────────────────────


class ProjectDetailView(DetailView):
    model = Project
    template_name = "projects/detail.html"
    context_object_name = "project"

    def get_queryset(self):
        base_qs = Project.objects.select_related(
            "genre", "created_by"
        ).prefetch_related("tags", "lyrics__author", "beats__producer", "vocal_tracks__vocalist")
        if self.request.user.is_authenticated:
            # Owner can see their own private projects
            return base_qs.filter(is_public=True) | base_qs.filter(
                created_by=self.request.user
            )
        return base_qs.filter(is_public=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = self.object
        ctx["lyrics_list"] = project.lyrics.select_related("author").order_by("-created_at")
        ctx["beats_list"] = project.beats.select_related("producer").order_by("-created_at")
        ctx["vocal_tracks_list"] = project.vocal_tracks.select_related("vocalist").order_by("-created_at")
        ctx["can_edit"] = (
            self.request.user.is_authenticated
            and self.request.user == project.created_by
        )
        ctx["lyrics_form"] = LyricsForm()
        ctx["beat_form"] = BeatSubmitForm()
        ctx["vocal_form"] = VocalSubmitForm()
        try:
            ctx["final_mix"] = project.final_mix
        except FinalMix.DoesNotExist:
            ctx["final_mix"] = None
        return ctx


# ── Create ─────────────────────────────────────────────────────────────────────


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        form._save_tags(self.object)
        messages.success(self.request, "¡Proyecto creado! Ahora busca colaboradores.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action"] = "Crear proyecto"
        ctx["page_title"] = "Nuevo Proyecto"
        return ctx


# ── Update ─────────────────────────────────────────────────────────────────────


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/form.html"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.created_by != self.request.user:
            raise PermissionDenied
        return obj

    def form_valid(self, form):
        response = super().form_valid(form)
        form._save_tags(self.object)
        messages.success(self.request, "Proyecto actualizado.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["action"] = "Guardar cambios"
        ctx["page_title"] = f"Editar: {self.object.title}"
        return ctx


# ── HTMX Partials ──────────────────────────────────────────────────────────────


@login_required
def submit_lyrics(request, slug):
    project = get_object_or_404(Project, slug=slug, is_public=True)

    if project.status != ProjectStatus.SEEKING_LYRICS:
        if _is_htmx(request):
            return HttpResponse(
                '<p class="text-red-400 text-sm">Este proyecto ya no acepta letras.</p>',
                status=400,
            )
        messages.error(request, "Este proyecto ya no acepta letras.")
        return redirect("projects:detail", slug=slug)

    if request.method == "POST":
        form = LyricsForm(request.POST)
        if form.is_valid():
            lyrics = form.save(commit=False)
            lyrics.project = project
            lyrics.author = request.user
            lyrics.save()
            if _is_htmx(request):
                return render(
                    request,
                    "projects/partials/lyrics_item.html",
                    {"lyrics": lyrics, "project": project, "can_select": False},
                )
            messages.success(request, "Letra enviada correctamente.")
            return redirect("projects:detail", slug=slug)
        if _is_htmx(request):
            return render(
                request,
                "projects/partials/lyrics_form.html",
                {"lyrics_form": form, "project": project},
                status=422,
            )

    if _is_htmx(request):
        return render(
            request,
            "projects/partials/lyrics_form.html",
            {"lyrics_form": LyricsForm(), "project": project},
        )
    return redirect("projects:detail", slug=slug)


@login_required
def submit_beat(request, slug):
    project = get_object_or_404(Project, slug=slug, is_public=True)

    if project.status != ProjectStatus.SEEKING_BEAT:
        if _is_htmx(request):
            return HttpResponse(
                '<p class="text-red-400 text-sm">Este proyecto ya no acepta beats.</p>',
                status=400,
            )
        messages.error(request, "Este proyecto ya no acepta beats.")
        return redirect("projects:detail", slug=slug)

    if request.method == "POST":
        form = BeatSubmitForm(request.POST, request.FILES)
        if form.is_valid():
            beat = form.save(commit=False)
            beat.project = project
            beat.producer = request.user
            beat.audio_format = request.FILES["original_file"].name.rsplit(".", 1)[-1].lower()
            beat.file_size = request.FILES["original_file"].size
            beat.save()
            if _is_htmx(request):
                return render(
                    request,
                    "projects/partials/beat_item.html",
                    {"beat": beat, "project": project, "can_select": False},
                )
            messages.success(request, "Beat enviado. Se está procesando.")
            return redirect("projects:detail", slug=slug)
        if _is_htmx(request):
            return render(
                request,
                "projects/partials/beat_form.html",
                {"beat_form": form, "project": project},
                status=422,
            )

    if _is_htmx(request):
        return render(
            request,
            "projects/partials/beat_form.html",
            {"beat_form": BeatSubmitForm(), "project": project},
        )
    return redirect("projects:detail", slug=slug)


@login_required
def submit_vocal(request, slug):
    project = get_object_or_404(Project, slug=slug, is_public=True)

    if project.status != ProjectStatus.SEEKING_VOCALS:
        if _is_htmx(request):
            return HttpResponse(
                '<p class="text-red-400 text-sm">Este proyecto ya no acepta vocales.</p>',
                status=400,
            )
        messages.error(request, "Este proyecto ya no acepta vocales.")
        return redirect("projects:detail", slug=slug)

    if request.method == "POST":
        form = VocalSubmitForm(request.POST, request.FILES)
        if form.is_valid():
            vocal = form.save(commit=False)
            vocal.project = project
            vocal.vocalist = request.user
            vocal.audio_format = request.FILES["original_file"].name.rsplit(".", 1)[-1].lower()
            vocal.file_size = request.FILES["original_file"].size
            vocal.save()
            if _is_htmx(request):
                return render(
                    request,
                    "projects/partials/vocal_item.html",
                    {"vocal": vocal, "project": project, "can_select": False},
                )
            messages.success(request, "Vocal enviado. Se está procesando.")
            return redirect("projects:detail", slug=slug)
        if _is_htmx(request):
            return render(
                request,
                "projects/partials/vocal_form.html",
                {"vocal_form": form, "project": project},
                status=422,
            )

    if _is_htmx(request):
        return render(
            request,
            "projects/partials/vocal_form.html",
            {"vocal_form": VocalSubmitForm(), "project": project},
        )
    return redirect("projects:detail", slug=slug)


@login_required
def select_contribution(request, slug, contribution_type, pk):
    """
    Mark a contribution as selected, deselect others of the same type,
    and advance the project state machine. Owner-only.
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    project = get_object_or_404(Project, slug=slug)
    if project.created_by != request.user:
        raise PermissionDenied

    STATUS_ADVANCE = {
        "lyrics": ProjectStatus.SEEKING_BEAT,
        "beat": ProjectStatus.SEEKING_VOCALS,
        "vocal": ProjectStatus.IN_REVIEW,
    }

    if contribution_type == "lyrics":
        project.lyrics.update(is_selected=False)
        obj = get_object_or_404(Lyrics, pk=pk, project=project)
        obj.is_selected = True
        obj.save(update_fields=["is_selected"])

    elif contribution_type == "beat":
        project.beats.update(is_selected=False)
        obj = get_object_or_404(Beat, pk=pk, project=project)
        obj.is_selected = True
        obj.save(update_fields=["is_selected"])

    elif contribution_type == "vocal":
        project.vocal_tracks.update(is_selected=False)
        obj = get_object_or_404(VocalTrack, pk=pk, project=project)
        obj.is_selected = True
        obj.save(update_fields=["is_selected"])

    else:
        return HttpResponse(status=400)

    next_status = STATUS_ADVANCE.get(contribution_type)
    try:
        if next_status:
            project.transition_to(next_status)
    except Exception:
        pass  # Already past this state or archived — fine

    messages.success(request, "Contribución seleccionada.")

    if _is_htmx(request):
        return HttpResponse(
            '<span class="inline-flex items-center gap-1 text-green-400 text-sm font-medium">'
            '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>'
            "</svg>Seleccionada</span>"
        )
    return redirect("projects:detail", slug=slug)
