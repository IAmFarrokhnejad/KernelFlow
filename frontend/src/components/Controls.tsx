import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
// ✅ removed unused Slider import

export default function Controls({
  selectedFilter, setSelectedFilter,
  useClientRaster, setUseClientRaster,
  customKernel, setCustomKernel
}: any) {

  const filters = [
    {value: "gaussian",    label: "Gaussian Filter"},
    {value: "median",      label: "Median Filter"},
    {value: "bilateral",   label: "Bilateral Filter"},
    {value: "nonlocal",    label: "Non-Local Means"},
    {value: "guided",      label: "Guided Filter"},
    {value: "unsharp",     label: "Unsharp Masking"},
    {value: "highboost",   label: "High-Boost Filtering"},
    {value: "log",         label: "LoG / Mexican Hat"},
    {value: "wiener",      label: "Wiener Deconvolution"},
    {value: "richardson",  label: "Richardson-Lucy"},
    {value: "custom",      label: "Custom 3×3 Mask"},
  ];

  return (
    <Card className="p-4 mt-4 space-y-6 bg-zinc-800 border-zinc-700">
      <Select value={selectedFilter} onValueChange={setSelectedFilter}>
        <SelectTrigger className="bg-zinc-700 border-zinc-600 text-white">
          <SelectValue />
        </SelectTrigger>
        {/* ✅ No position prop (not Base UI API); explicit colors fix invisible items */}
        <SelectContent className="bg-zinc-800 border-zinc-600 text-white z-50">
          {filters.map(f => (
            <SelectItem
              key={f.value}
              value={f.value}
              className="text-white hover:bg-zinc-600 focus:bg-zinc-600 cursor-pointer"
            >
              {f.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div>
        <label className="text-sm text-zinc-300">3×3 Custom Kernel (only for Custom mode)</label>
        <div className="grid grid-cols-3 gap-1 mt-2">
          {customKernel.flat().map((v: number, i: number) => (
            <input key={i} type="number" step="0.1" value={v}
              onChange={e => {
                const arr = [...customKernel.flat()];
                arr[i] = parseFloat(e.target.value);
                setCustomKernel([[arr[0],arr[1],arr[2]],[arr[3],arr[4],arr[5]],[arr[6],arr[7],arr[8]]]);
              }}
              className="w-full text-center border border-zinc-600 bg-zinc-900 text-white rounded p-1"
            />
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Checkbox id="client" checked={useClientRaster} onCheckedChange={setUseClientRaster} />
        <label htmlFor="client" className="text-sm text-zinc-300 cursor-pointer">
          Use Client-side Raster (fast 3×3 filters)
        </label>
      </div>

      <Button variant="secondary" className="w-full" onClick={() => window.alert("Boost slider etc. can be added here")}>
        Adjust Strength / KSize
      </Button>
    </Card>
  );
}