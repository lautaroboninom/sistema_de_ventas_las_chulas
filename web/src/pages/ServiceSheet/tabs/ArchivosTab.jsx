import IngresoPhotos from "../../../components/IngresoPhotos";

export default function ArchivosTab({ id, canManagePhotos }) {
  return (
    <div className="border rounded p-4">
      <h2 className="font-semibold mb-2">Archivos</h2>
      <p className="text-gray-600 mb-3">Imágenes, PDF y videos cortos</p>
      <IngresoPhotos ingresoId={Number(id)} canManage={canManagePhotos} showFilters />
    </div>
  );
}

