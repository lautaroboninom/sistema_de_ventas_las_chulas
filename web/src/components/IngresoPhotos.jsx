import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getIngresoFotos,
  uploadIngresoFotos,
  patchIngresoFoto,
  deleteIngresoFoto,
  fetchBlobAuth,
  downloadAuth,
} from "../lib/api";
import { formatDateTime } from "../lib/ui-helpers";

const PAGE_SIZE = 20;

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let idx = 0;
  let value = bytes;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  return `${value.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export default function IngresoPhotos({ ingresoId, canManage }) {
  const [photos, setPhotos] = useState([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadErrors, setUploadErrors] = useState([]);
  const [statusMessage, setStatusMessage] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [commentDraft, setCommentDraft] = useState("");
  const fileInputRef = useRef(null);

  const [viewer, setViewer] = useState({ open: false, index: 0, zoom: 1, rotation: 0 });
  // Blob URLs para miniaturas y archivos completos
  const thumbUrlsRef = useRef(new Map()); // id -> objectURL
  const fullUrlsRef = useRef(new Map());  // id -> objectURL
  const [thumbSrc, setThumbSrc] = useState({}); // id -> objectURL
  const [fullSrc, setFullSrc] = useState({});   // id -> objectURL

  const currentPhoto = useMemo(() => (viewer.open ? photos[viewer.index] : null), [viewer, photos]);

  const resetViewer = useCallback(() => {
    setViewer({ open: false, index: 0, zoom: 1, rotation: 0 });
  }, []);

  const loadPhotos = useCallback(async (targetPage = 1, append = false) => {
    if (!ingresoId) return;
    setLoading(true);
    setError("");
    try {
      const data = await getIngresoFotos(ingresoId, { page: targetPage, page_size: PAGE_SIZE });
      const list = Array.isArray(data?.results) ? data.results : [];
      setPhotos((prev) => (append ? [...prev, ...list] : list));
      setPage(data?.page || targetPage);
      setHasMore(Boolean(data?.has_next));
      // Pre-cargar miniaturas autenticadas como blob URLs
      if (!append) {
        thumbUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
        thumbUrlsRef.current.clear();
        setThumbSrc({});
      }
      const promises = list.map(async (p) => {
        try {
          const { blob } = await fetchBlobAuth(p.thumbnail_url);
          const url = URL.createObjectURL(blob);
          const prevUrl = thumbUrlsRef.current.get(p.id);
          if (prevUrl) URL.revokeObjectURL(prevUrl);
          thumbUrlsRef.current.set(p.id, url);
          setThumbSrc((prev) => ({ ...prev, [p.id]: url }));
        } catch (_) {
          // ignorar errores individuales
        }
      });
      Promise.allSettled(promises);
    } catch (err) {
      setError(err?.message || "No se pudieron cargar las fotos");
    } finally {
      setLoading(false);
    }
  }, [ingresoId]);

  useEffect(() => {
    if (!ingresoId) return;
    loadPhotos(1, false);
  }, [ingresoId, loadPhotos]);

  useEffect(() => {
    if (viewer.open && viewer.index >= photos.length) {
      if (photos.length === 0) {
        resetViewer();
      } else {
        setViewer((prev) => ({ ...prev, index: Math.max(photos.length - 1, 0) }));
      }
    }
  }, [photos, viewer, resetViewer]);

  // Asegurar carga de imagen completa (hoisted declaration to avoid TDZ in effects)
  function ensureFullLoaded(photo) {
    if (!photo) return;
    const id = photo.id;
    if (fullUrlsRef.current.has(id)) return;
    fetchBlobAuth(photo.url)
      .then(({ blob }) => {
        const url = URL.createObjectURL(blob);
        fullUrlsRef.current.set(id, url);
        setFullSrc((prev) => ({ ...prev, [id]: url }));
      })
      .catch(() => {
        // fallback: se verá la miniatura
      });
  }

  // Cargar imagen completa al navegar en el visor
  useEffect(() => {
    if (!viewer.open) return;
    const p = photos[viewer.index];
    if (p) ensureFullLoaded(p);
  }, [viewer.open, viewer.index, photos, ensureFullLoaded]);

  const handleUpload = async (fileList) => {
    const files = Array.from(fileList || []).filter((f) => f && f.size);
    if (!files.length) return;
    setUploading(true);
    setUploadErrors([]);
    setStatusMessage("");
    try {
      const data = await uploadIngresoFotos(ingresoId, files);
      const errs = Array.isArray(data?.errors) ? data.errors : [];
      if (errs.length) {
        setUploadErrors(errs.map((e) => e?.detail || e?.name || "No se pudo subir el archivo"));
      } else {
        setUploadErrors([]);
      }
      await loadPhotos(1, false);
      setStatusMessage("Fotos subidas correctamente");
    } catch (err) {
      setUploadErrors([err?.message || "No se pudo subir la foto"]);
    } finally {
      setUploading(false);
    }
  };

  const onFileChange = (event) => {
    handleUpload(event.target.files);
    event.target.value = "";
  };

  const onDrop = (event) => {
    event.preventDefault();
    if (!canManage) return;
    handleUpload(event.dataTransfer.files);
  };

  const onDragOver = (event) => {
    if (!canManage) return;
    event.preventDefault();
  };

  const startEditing = (photo) => {
    setEditingId(photo.id);
    setCommentDraft(photo.comentario || "");
  };

  const cancelEditing = () => {
    setEditingId(null);
    setCommentDraft("");
  };

  const saveComment = async (photoId) => {
    try {
      const payload = { comentario: commentDraft };
      const updated = await patchIngresoFoto(ingresoId, photoId, payload);
      setPhotos((prev) => prev.map((p) => (p.id === photoId ? updated : p)));
      cancelEditing();
      setStatusMessage("Comentario actualizado");
    } catch (err) {
      setUploadErrors([err?.message || "No se pudo guardar el comentario"]);
    }
  };

  const confirmDelete = async (photoId) => {
    if (!window.confirm("¿Eliminar la foto seleccionada?")) return;
    try {
      await deleteIngresoFoto(ingresoId, photoId);
      setPhotos((prev) => prev.filter((p) => p.id !== photoId));
      setStatusMessage("Foto eliminada");
      // Revocar y limpiar URLs asociadas a la foto eliminada
      const t = thumbUrlsRef.current.get(photoId);
      if (t) {
        URL.revokeObjectURL(t);
        thumbUrlsRef.current.delete(photoId);
      }
      const f = fullUrlsRef.current.get(photoId);
      if (f) {
        URL.revokeObjectURL(f);
        fullUrlsRef.current.delete(photoId);
      }
      setThumbSrc((prev) => {
        const next = { ...prev };
        delete next[photoId];
        return next;
      });
      setFullSrc((prev) => {
        const next = { ...prev };
        delete next[photoId];
        return next;
      });
    } catch (err) {
      setUploadErrors([err?.message || "No se pudo eliminar la foto"]);
    }
  };


  const openViewer = (index) => {
    setViewer({ open: true, index, zoom: 1, rotation: 0 });
    const p = photos[index];
    if (p) ensureFullLoaded(p);
  };

  const changeViewerIndex = (delta) => {
    setViewer((prev) => {
      const next = prev.index + delta;
      if (next < 0 || next >= photos.length) return prev;
      return { ...prev, index: next, zoom: 1, rotation: 0 };
    });
  };

  const adjustZoom = (amount) => {
    setViewer((prev) => {
      const nextZoom = Math.min(3, Math.max(0.5, Number((prev.zoom + amount).toFixed(2))));
      return { ...prev, zoom: nextZoom };
    });
  };

  const rotate = () => {
    setViewer((prev) => ({ ...prev, rotation: (prev.rotation + 90) % 360 }));
  };

  const handleDownload = async (photo) => {
    if (!photo) return;
    try {
      await downloadAuth(photo.url, photo.original_name || `ingreso-${ingresoId}-foto-${photo.id}`);
    } catch (err) {
      setUploadErrors([err?.message || "No se pudo descargar la foto"]);
    }
  };

  // Limpiar todos los Object URLs al desmontar
  useEffect(() => {
    return () => {
      try {
        thumbUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
        fullUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      } finally {
        thumbUrlsRef.current.clear();
        fullUrlsRef.current.clear();
      }
    };
  }, []);

  return (
    <div className="border rounded p-4 mt-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">Fotos del equipo (Ingreso)</h3>
          <p className="text-sm text-gray-600">
            Subí imágenes para documentar estado, roturas y condiciones de recepción.
          </p>
        </div>
        {canManage && (
          <button
            className="bg-blue-600 text-white px-3 py-2 rounded"
            onClick={() => fileInputRef.current?.click()}
            type="button"
            disabled={uploading}
          >
            {uploading ? "Subiendo..." : "Cargar fotos"}
          </button>
        )}
      </div>

      {canManage && (
        <div
          className="mt-3 border-2 border-dashed border-blue-300 rounded bg-blue-50 p-4 text-sm text-gray-600"
          onDrop={onDrop}
          onDragOver={onDragOver}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={onFileChange}
          />
          <p className="font-medium">Arrastrá y soltá fotos acá o usá el botón "Cargar fotos".</p>
          <p className="mt-1 text-xs text-gray-500">
            Formatos permitidos: JPG/PNG (máx. 10 MB por archivo, hasta 50 fotos por ingreso).
          </p>
        </div>
      )}

      {statusMessage && (
        <div className="mt-3 text-sm text-green-700 bg-green-100 border border-green-200 px-3 py-2 rounded">
          {statusMessage}
        </div>
      )}
      {uploadErrors.length > 0 && (
        <div className="mt-3 text-sm text-red-700 bg-red-100 border border-red-200 px-3 py-2 rounded">
          <ul className="list-disc list-inside">
            {uploadErrors.map((msg, idx) => (
              <li key={idx}>{msg}</li>
            ))}
          </ul>
        </div>
      )}
      {error && (
        <div className="mt-3 text-sm text-red-700 bg-red-100 border border-red-200 px-3 py-2 rounded">
          {error}
        </div>
      )}

      <div className="mt-4 space-y-3">
        {loading && photos.length === 0 && (
          <div className="text-sm text-gray-500">Cargando fotos...</div>
        )}
        {!loading && photos.length === 0 && (
          <div className="text-sm text-gray-500">Aún no hay fotos asociadas a este ingreso.</div>
        )}
          
        {photos.map((photo, idx) => (
          <div key={photo.id} className="flex flex-col md:flex-row gap-3 border rounded p-3 bg-white">
            <div className="w-full md:w-28 md:h-28 flex-shrink-0 flex items-center justify-center bg-gray-100 rounded cursor-pointer overflow-hidden">
              <img
                src={thumbSrc[photo.id] || ""}
                alt={photo.original_name || `Foto ${photo.id}`}
                className="object-cover w-full h-full"
                onClick={() => openViewer(idx)}
              />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-600">
                <span className="font-medium text-gray-900">{photo.original_name || `Foto ${photo.id}`}</span>
                <span>{formatDateTime(photo.created_at)}</span>
                <span>{photo.usuario_nombre || "-"}</span>
                <span>{formatBytes(photo.size_bytes)}</span>
                <span>{photo.width}x{photo.height}px</span>
              </div>
              {editingId === photo.id ? (
                <div className="mt-3 space-y-2">
                  <textarea
                    className="w-full border rounded p-2 text-sm"
                    rows={3}
                    value={commentDraft}
                    onChange={(e) => setCommentDraft(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <button
                      className="bg-blue-600 text-white px-3 py-1 rounded"
                      onClick={() => saveComment(photo.id)}
                      type="button"
                    >
                      Guardar
                    </button>
                    <button
                      className="px-3 py-1 rounded border"
                      onClick={cancelEditing}
                      type="button"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-2 text-sm text-gray-700 whitespace-pre-wrap">
                  {photo.comentario ? photo.comentario : <span className="text-gray-400 italic">Sin comentario</span>}
                </div>
              )}
              {canManage && editingId !== photo.id && (
                <div className="flex gap-3 mt-3 text-sm">
                  <button className="text-blue-600" onClick={() => startEditing(photo)} type="button">
                    {photo.comentario ? "Editar comentario" : "Agregar comentario"}
                  </button>
                  <button className="text-red-600" onClick={() => confirmDelete(photo.id)} type="button">
                    Eliminar
                  </button>
                  <button className="text-gray-600" onClick={() => handleDownload(photo)} type="button">
                    Descargar
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {hasMore && (
        <div className="mt-4 text-center">
          <button
            className="px-3 py-2 border rounded"
            onClick={() => loadPhotos(page + 1, true)}
            type="button"
            disabled={loading}
          >
            {loading ? "Cargando..." : "Ver más"}
          </button>
        </div>
      )}

      {viewer.open && currentPhoto && (
        <div className="fixed inset-0 bg-black/80 z-40 flex flex-col items-center justify-center p-6">
          <div className="flex justify-between items-center w-full max-w-4xl text-white mb-4">
            <div>
              <div className="font-semibold">{currentPhoto.original_name || `Foto ${currentPhoto.id}`}</div>
              <div className="text-sm text-gray-300">{formatDateTime(currentPhoto.created_at)}</div>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-1 bg-gray-700 rounded" onClick={() => adjustZoom(0.25)} type="button">Zoom +</button>
              <button className="px-3 py-1 bg-gray-700 rounded" onClick={() => adjustZoom(-0.25)} type="button">Zoom -</button>
              <button className="px-3 py-1 bg-gray-700 rounded" onClick={rotate} type="button">Rotar</button>
              <button className="px-3 py-1 bg-gray-700 rounded" onClick={() => handleDownload(currentPhoto)} type="button">
                Descargar
              </button>
              <button className="px-3 py-1 bg-red-600 rounded" onClick={resetViewer} type="button">Cerrar</button>
            </div>
          </div>
          <div className="relative max-w-4xl max-h-[70vh] overflow-auto bg-black/40 rounded">
            <img
              src={fullSrc[currentPhoto.id] || thumbSrc[currentPhoto.id] || ""}
              alt={currentPhoto.original_name || `Foto ${currentPhoto.id}`}
              style={{ transform: `scale(${viewer.zoom}) rotate(${viewer.rotation}deg)` }}
              className="max-w-full max-h-[70vh] object-contain transition-transform duration-200"
            />
          </div>
          <div className="flex gap-4 text-white mt-4">
            <button
              className="px-3 py-1 bg-gray-700 rounded"
              onClick={() => changeViewerIndex(-1)}
              disabled={viewer.index === 0}
              type="button"
            >
              Anterior
            </button>
            <button
              className="px-3 py-1 bg-gray-700 rounded"
              onClick={() => changeViewerIndex(1)}
              disabled={viewer.index >= photos.length - 1}
              type="button"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}
    </div>
  );
}




