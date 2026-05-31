#!/bin/bash
# versiona.sh — Automazione release per PCM (Python Connection Manager)
# La versione è il numero progressivo di commit git (non semver).
# Uso: bash versiona.sh [--dry-run]
# Opzionale: ANTHROPIC_API_KEY per note di rilascio generate con AI.

set -e

# ── Colori ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info() { echo -e "${CYAN}ℹ ${RESET}$*"; }
ok()   { echo -e "${GREEN}✔ ${RESET}$*"; }
warn() { echo -e "${YELLOW}⚠ ${RESET}$*" >&2; }
err()  { echo -e "${RED}✘ ${RESET}$*" >&2; exit 1; }
sep()  { echo -e "${BOLD}──────────────────────────────────────────────${RESET}"; }

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# ── Verifica git ──────────────────────────────────────────────────────────────
git rev-parse --git-dir &>/dev/null || err "Non sei in un repository git."
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PROJECT_NAME="PCM"

# ── Rileva branch principale ──────────────────────────────────────────────────
detect_main_branch() {
    local ref
    ref=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|.*/||' || true)
    [[ -n "$ref" ]] && echo "$ref" && return
    for b in main master; do
        git show-ref --verify --quiet "refs/heads/$b" && echo "$b" && return
    done
    git rev-parse --abbrev-ref HEAD
}
MAIN_BRANCH=$(detect_main_branch)

# ── Rileva piattaforma remote ─────────────────────────────────────────────────
detect_platform() {
    local url
    url=$(git remote get-url origin 2>/dev/null || true)
    if   [[ "$url" == *"github.com"* ]]; then echo "github"
    elif [[ "$url" == *"gitlab"* ]];     then echo "gitlab"
    else                                      echo "none"
    fi
}
PLATFORM=$(detect_platform)

# ── Versione = numero di commit progressivo ───────────────────────────────────
# Viene calcolata DOPO il commit di release, quindi +1 rispetto allo stato attuale.
COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null) || err "Impossibile contare i commit."
VERSION=$(( COMMIT_COUNT + 1 ))   # +1 perché includerà il commit "chore: release"
TAG_VERSION="v${VERSION}"

# ── Analisi commit dall'ultimo tag ────────────────────────────────────────────
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [[ -z "$LATEST_TAG" ]]; then
    RAW_COMMITS=$(git log --pretty=tformat:"---commit---%n%B" --no-merges || true)
else
    RAW_COMMITS=$(git log "${LATEST_TAG}..HEAD" --pretty=tformat:"---commit---%n%B" --no-merges || true)
fi

FILTERED_COMMITS=$(echo "$RAW_COMMITS" | grep -Eiv "^chore: (release|bump|version) " || true)

# ── Genera note di rilascio ───────────────────────────────────────────────────
generate_release_notes() {
    local commits="$1" version="$2"
    local prompt="Trasforma i seguenti commit message git in note di rilascio professionali per ${PROJECT_NAME} build ${version}.

Istruzioni:
- Scrivi in italiano
- Raggruppa per categoria con questi titoli (includi solo quelle presenti):
  ## 🆕 Nuove funzionalità
  ## ⚡ Miglioramenti
  ## 🐛 Correzioni di bug
  ## 🔧 Manutenzione
- Ogni voce come elenco puntato con •
- Linguaggio chiaro, orientato all'utente finale
- Ometti commit di tipo 'chore: release', 'chore: bump', 'chore: version'
- Massimo 2 righe per voce, inizia direttamente con le categorie

Commit:
${commits}"

    if command -v curl &>/dev/null && command -v jq &>/dev/null && [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
        info "Generazione note con Claude AI..." >&2
        local payload result
        payload=$(jq -n --arg txt "$prompt" '{
            model: "claude-haiku-4-5-20251001",
            max_tokens: 2048,
            messages: [{"role": "user", "content": $txt}]
        }')
        result=$(curl -sf --max-time 30 -X POST "https://api.anthropic.com/v1/messages" \
            -H "x-api-key: $ANTHROPIC_API_KEY" \
            -H "anthropic-version: 2023-06-01" \
            -H "content-type: application/json" \
            -d "$payload" | jq -r '.content[0].text' 2>/dev/null || true)
        if [[ -n "$result" && "$result" != "null" ]]; then
            ok "Note generate con AI." >&2
            echo "$result"; return 0
        fi
        warn "Claude API non raggiungibile o chiave non valida; uso formattazione base."
    else
        warn "AI non disponibile (curl/jq mancanti o ANTHROPIC_API_KEY non impostata); uso formattazione base."
    fi

    # Fallback: raggruppa per tipo conventional commit
    local feat="" fix="" perf="" other=""
    while IFS= read -r subj; do
        local clean
        clean=$(printf '%s' "$subj" | sed -E 's/^[a-z]+(\([^)]+\))?: //')
        if   [[ "$subj" =~ ^feat  ]]; then feat+="• $clean"$'\n'
        elif [[ "$subj" =~ ^fix   ]]; then fix+="• $clean"$'\n'
        elif [[ "$subj" =~ ^perf  ]]; then perf+="• $clean"$'\n'
        else                               other+="• $clean"$'\n'
        fi
    done < <(
        echo "$commits" \
            | awk '/^---commit---/ { if (s != "") print s; s = ""; next }
                   /^[[:space:]]*$/ { next }
                   s == ""          { s = $0 }
                   END              { if (s != "") print s }' \
            | grep -Eiv "^chore: (release|bump|version)" || true
    )

    local out=""
    [[ -n "$feat"  ]] && out+=$'## 🆕 Nuove funzionalità\n'"$feat"$'\n'
    [[ -n "$perf"  ]] && out+=$'## ⚡ Miglioramenti\n'"$perf"$'\n'
    [[ -n "$fix"   ]] && out+=$'## 🐛 Correzioni di bug\n'"$fix"$'\n'
    [[ -n "$other" ]] && out+=$'## 🔧 Manutenzione\n'"$other"$'\n'
    echo "${out%$'\n'}"
}

# ── Pubblica release sulla piattaforma rilevata ───────────────────────────────
publish_release() {
    local tag="$1" version="$2" notes_file="$3"
    case "$PLATFORM" in
        github)
            if command -v gh &>/dev/null; then
                gh release create "$tag" \
                    --title "${PROJECT_NAME} build ${version}" \
                    --notes-file "$notes_file"
                ok "Release pubblicata su GitHub."
            else
                warn "GitHub CLI (gh) non trovata. Pubblica manualmente su:"
                echo "  https://github.com/$(git remote get-url origin 2>/dev/null | sed 's|.*github.com[:/]||;s|\.git$||')/releases"
                _print_notes_fallback "$version" "$notes_file"
            fi ;;
        gitlab)
            if command -v glab &>/dev/null; then
                glab release create "$tag" \
                    --name "${PROJECT_NAME} build ${version}" \
                    --notes-file "$notes_file"
                ok "Release pubblicata su GitLab."
            else
                warn "GitLab CLI (glab) non trovata. Pubblica manualmente su GitLab → Releases."
                _print_notes_fallback "$version" "$notes_file"
            fi ;;
        none)
            warn "Nessun remote rilevato; il tag è solo locale."
            _print_notes_fallback "$version" "$notes_file" ;;
    esac
}

_print_notes_fallback() {
    local version="$1" notes_file="$2"
    echo ""
    echo "── Note di rilascio ──────────────────────────────────"
    echo "## ${PROJECT_NAME} build ${version}"
    echo ""
    cat "$notes_file"
    echo "──────────────────────────────────────────────────────"
}

# ═════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}=== Release: ${PROJECT_NAME} === branch: ${MAIN_BRANCH} === ${PLATFORM} ===${RESET}"
$DRY_RUN && echo -e "${YELLOW}[DRY RUN — nessuna modifica verrà applicata]${RESET}"
echo ""
info "Versione (numero commit dopo release): ${BOLD}${VERSION}${RESET}  →  tag ${BOLD}${TAG_VERSION}${RESET}"
info "Commit analizzati dal tag: ${BOLD}${LATEST_TAG:-inizio repo}${RESET}"
echo ""

# ── Genera note ───────────────────────────────────────────────────────────────
if [[ -z "${FILTERED_COMMITS// }" ]]; then
    CHANGELOG="• nessun commit trovato"
else
    CHANGELOG=$(generate_release_notes "$FILTERED_COMMITS" "$VERSION")
fi

# ── Anteprima e conferma ──────────────────────────────────────────────────────
while true; do
    echo ""
    sep
    echo -e "${BOLD}Note di rilascio per ${PROJECT_NAME} build ${VERSION}:${RESET}"
    sep
    echo ""
    echo "$CHANGELOG"
    echo ""
    sep
    echo ""
    read -rp "$(echo -e "Continuare con la release build ${BOLD}${VERSION}${RESET}? [s(i)/N(o)/e(dita note)] ")" CONFIRM
    CONFIRM=${CONFIRM:-N}
    if [[ "${CONFIRM,,}" == "n" ]]; then
        warn "Release annullata."
        exit 0
    elif [[ "${CONFIRM,,}" == "e" ]]; then
        TMP_EDIT=$(mktemp /tmp/versiona_edit_XXXX.md)
        echo "$CHANGELOG" > "$TMP_EDIT"
        ${EDITOR:-nano} "$TMP_EDIT"
        CHANGELOG=$(cat "$TMP_EDIT")
        rm -f "$TMP_EDIT"
        info "Note di rilascio modificate."
    elif [[ "${CONFIRM,,}" == "s" ]]; then
        break
    else
        echo -e "${YELLOW}Scelta non valida. Inserisci s (sì), n (no) o e (edita).${RESET}"
    fi
done

$DRY_RUN && { ok "[DRY RUN] Nessuna modifica applicata. Uscita."; exit 0; }

# ── Commit di release ─────────────────────────────────────────────────────────
info "Creazione commit di release..."
git commit -m "chore: release ${VERSION}" --allow-empty
ok "Commit creato. Numero commit totale: $(git rev-list --count HEAD)"

# ── Tag annotato ──────────────────────────────────────────────────────────────
info "Creazione tag ${TAG_VERSION}..."
git tag -a "$TAG_VERSION" -m "$(printf '%s build %s\n\n%s' "$PROJECT_NAME" "$VERSION" "$CHANGELOG")"
ok "Tag ${TAG_VERSION} creato."

# ── Push ──────────────────────────────────────────────────────────────────────
info "Push di ${MAIN_BRANCH} e tag..."
git push origin "$MAIN_BRANCH"
git push origin "$TAG_VERSION"
ok "Push completato."

# ── Pubblicazione release ─────────────────────────────────────────────────────
echo ""
info "Pubblicazione release..."
NOTES_FILE=$(mktemp /tmp/release_notes_XXXX.md)
printf '## %s build %s\n\n%s\n' "$PROJECT_NAME" "$VERSION" "$CHANGELOG" > "$NOTES_FILE"
publish_release "$TAG_VERSION" "$VERSION" "$NOTES_FILE"
rm -f "$NOTES_FILE"

# ── Build AppImage locale + upload alla release ───────────────────────────────
APPIMAGE_BUILD_SCRIPT="packaging/appimage/build-appimage.sh"
if [[ -f "$APPIMAGE_BUILD_SCRIPT" ]]; then
    echo ""
    sep
    read -rp "$(echo -e "Avviare la ${BOLD}build AppImage${RESET} locale ora? [s/N] ")" DO_APPIMAGE
    DO_APPIMAGE=${DO_APPIMAGE:-N}
    if [[ "${DO_APPIMAGE,,}" == "s" ]]; then
        info "Avvio build AppImage (versione ${VERSION})..."
        bash "$APPIMAGE_BUILD_SCRIPT" "$VERSION"
        APPIMAGE_FILE=$(ls dist/PCM-${VERSION}-*.AppImage 2>/dev/null | head -1 || true)
        if [[ -z "$APPIMAGE_FILE" ]]; then
            warn "AppImage non trovata in dist/. Upload saltato."
        else
            ok "AppImage prodotta: ${APPIMAGE_FILE} ($(du -sh "${APPIMAGE_FILE}" | cut -f1))"
            if command -v gh >/dev/null 2>&1; then
                info "Caricamento ${APPIMAGE_FILE} nella release ${TAG_VERSION}..."
                _upload_ok=false
                if command -v curl >/dev/null 2>&1; then
                    _slug=$(git remote get-url origin 2>/dev/null | sed 's|.*github.com[:/]||;s|\.git$||')
                    _rel_id=$(gh api "repos/${_slug}/releases/tags/${TAG_VERSION}" --jq '.id' 2>/dev/null || true)
                    _token=$(gh auth token 2>/dev/null || true)
                    _fname=$(basename "${APPIMAGE_FILE}")
                    if [[ -n "$_rel_id" && -n "$_token" ]]; then
                        _aid=$(gh api "repos/${_slug}/releases/${_rel_id}/assets" \
                            --jq ".[] | select(.name==\"${_fname}\") | .id" 2>/dev/null || true)
                        [[ -n "$_aid" ]] && \
                            gh api --method DELETE "repos/${_slug}/releases/assets/${_aid}" >/dev/null 2>&1 || true
                        _up_url="https://uploads.github.com/repos/${_slug}/releases/${_rel_id}/assets?name=${_fname}"
                        _http=$(curl -# -X POST \
                            -H "Authorization: token ${_token}" \
                            -H "Content-Type: application/octet-stream" \
                            "${_up_url}" --data-binary @"${APPIMAGE_FILE}" \
                            -w "%{http_code}" -o /dev/null)
                        [[ "$_http" == "201" ]] && _upload_ok=true
                    fi
                fi
                $_upload_ok || { gh release upload "${TAG_VERSION}" "${APPIMAGE_FILE}" --clobber && _upload_ok=true || true; }
                $_upload_ok && ok "AppImage caricata nella release ${TAG_VERSION}." || \
                    warn "Upload fallito. Carica manualmente: ${APPIMAGE_FILE}"
            else
                warn "gh CLI non trovata. Carica manualmente l'AppImage nella release:"
                echo "  ${APPIMAGE_FILE}"
            fi
        fi
    else
        info "Build AppImage saltata. Per compilare manualmente:"
        echo "  bash packaging/appimage/build-appimage.sh ${VERSION}"
    fi
fi

# ── Build Linux (deb + tar.gz) opzionale ─────────────────────────────────────
LINUX_BUILD_SCRIPT="linuxbuild/build.sh"
if [[ -f "$LINUX_BUILD_SCRIPT" ]]; then
    echo ""
    sep
    read -rp "$(echo -e "Avviare la ${BOLD}build Linux${RESET} (deb + tar.gz) ora? [s/N] ")" DO_LINUX
    DO_LINUX=${DO_LINUX:-N}
    if [[ "${DO_LINUX,,}" == "s" ]]; then
        info "Avvio build Linux (versione ${VERSION})..."
        bash "$LINUX_BUILD_SCRIPT" "$VERSION"
    else
        info "Build Linux saltata. Per compilare manualmente:"
        echo "  bash linuxbuild/build.sh ${VERSION}"
    fi
fi

# ── Pulizia artefatti ────────────────────────────────────────────────────────
sep
info "Pulizia artefatti di build..."
rm -rf "$REPO_ROOT/build/" "$REPO_ROOT/.venv-build/" \
       "$REPO_ROOT/gtk3/__pycache__/" "$REPO_ROOT/__pycache__/"
ok "Pulizia completata."

echo ""
echo -e "${GREEN}${BOLD}=== ✔  ${PROJECT_NAME} build ${VERSION} rilasciato con successo! ===${RESET}"
echo ""
