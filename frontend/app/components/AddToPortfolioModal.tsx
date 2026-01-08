import { useState, useEffect } from 'react'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { Minus, Wallet, Link as LinkIcon, Loader2 } from 'lucide-react'
// Animated icons
import { XIcon } from '~/components/ui/x'
import { PlusIcon } from '~/components/ui/plus'
import { CheckIcon } from '~/components/ui/check'
import clsx from 'clsx'
import { SimpleDropdown } from './ui/dropdown'
import { useModalAccessibility } from '~/hooks/useFocusTrap'

type CardInfo = {
    id: number
    name: string
    set_name: string
    floor_price?: number
    latest_price?: number
    product_type?: string  // Single, Box, Pack, Bundle, Proof, Lot, NFT
    image_url?: string  // Card thumbnail URL
}

type AddToPortfolioDrawerProps = {
    card: CardInfo
    isOpen: boolean
    onClose: () => void
}

type PortfolioCardCreate = {
    card_id: number
    treatment: string
    source: string
    purchase_price: number
    purchase_date: string | null
    grading: string | null
    notes: string | null
    quantity?: number
}

type TreatmentPricing = {
    treatment: string
    fmp: number | null
    floor_price: number | null
    sales_count: number
    median_price: number | null
    min_price: number | null
    max_price: number | null
    avg_price: number | null
}

type CardPricingResponse = {
    card_id: number
    card_name: string
    fair_market_price: number | null
    floor_price: number | null
    by_treatment: TreatmentPricing[]
}

// Actual WOTF card treatments by product type
const TREATMENTS_BY_TYPE: Record<string, string[]> = {
    'Single': [
        'Classic Paper', 'Classic Foil',
        'Full Art', 'Full Art Foil',
        'Formless', 'Formless Foil',
        'Serialized',
        '1st Edition', '1st Edition Foil',
        'Promo', 'Prerelease'
    ],
    'Box': ['Sealed', 'Opened'],
    'Pack': ['Sealed', 'Opened'],
    'Bundle': ['Sealed', 'Opened'],
    'Lot': ['Mixed', 'All Sealed', 'All Raw'],
    'Proof': ['Character Proof', 'Set Proof', 'Other'],
    'NFT': ['Standard', 'Animated', 'Legendary', '1/1'],
    'default': [
        'Classic Paper', 'Classic Foil',
        'Full Art', 'Full Art Foil',
        'Formless', 'Formless Foil',
        'Serialized',
        '1st Edition', '1st Edition Foil',
        'Promo', 'Prerelease'
    ]
}

// Source options by product type
const SOURCES_BY_TYPE: Record<string, string[]> = {
    'NFT': ['OpenSea', 'Blur', 'Magic Eden', 'Other'],
    'default': ['eBay', 'Blokpax', 'TCGPlayer', 'LGS', 'Trade', 'Pack Pull', 'Other']
}

// Parse OpenSea URL to extract details
const parseOpenSeaUrl = (url: string): { chain?: string; contract?: string; tokenId?: string; valid: boolean } => {
    try {
        // Format: https://opensea.io/item/ethereum/0x28a11da34a93712b1fde4ad15da217a3b14d9465/4294968598
        const regex = /opensea\.io\/(?:assets|item)\/([^\/]+)\/([^\/]+)\/(\d+)/
        const match = url.match(regex)
        if (match) {
            return {
                chain: match[1],
                contract: match[2],
                tokenId: match[3],
                valid: true
            }
        }
        return { valid: false }
    } catch {
        return { valid: false }
    }
}

export function AddToPortfolioModal({ card, isOpen, onClose }: AddToPortfolioDrawerProps) {
    // Accessibility: focus trap, scroll lock, escape to close
    const { containerRef, modalProps } = useModalAccessibility(isOpen, {
        onClose,
        initialFocus: 'input[name="purchase_price"]', // Focus price input on open
    })

    const queryClient = useQueryClient()
    const productType = card.product_type || 'Single'
    const isNFT = productType === 'NFT' || productType === 'Proof'

    // Get treatment and source options based on product type
    const treatmentOptions = TREATMENTS_BY_TYPE[productType] || TREATMENTS_BY_TYPE['default']
    const sourceOptions = isNFT ? SOURCES_BY_TYPE['NFT'] : SOURCES_BY_TYPE['default']
    const defaultTreatment = treatmentOptions[0]
    const defaultSource = sourceOptions[0]

    // Fetch treatment-specific pricing data
    const { data: pricingData } = useQuery({
        queryKey: ['card-pricing', card.id],
        queryFn: async () => {
            return await api.get(`cards/${card.id}/pricing`).json<CardPricingResponse>()
        },
        enabled: isOpen && !!card.id,
        staleTime: 60000, // Cache for 1 minute
    })

    // Get pricing for selected treatment
    const getTreatmentPricing = (treatment: string): TreatmentPricing | null => {
        if (!pricingData?.by_treatment) return null
        return pricingData.by_treatment.find(t => t.treatment === treatment) || null
    }

    // Get suggested price for a treatment
    const getSuggestedPrice = (treatment: string): number => {
        const treatmentPricing = getTreatmentPricing(treatment)
        if (treatmentPricing) {
            // Priority: floor_price > fmp > median > avg > min
            return treatmentPricing.floor_price ||
                   treatmentPricing.fmp ||
                   treatmentPricing.median_price ||
                   treatmentPricing.avg_price ||
                   treatmentPricing.min_price ||
                   0
        }
        // Fallback to card-level pricing
        return pricingData?.floor_price || card.floor_price || card.latest_price || 0
    }

    // Single card form
    const [form, setForm] = useState({
        treatment: defaultTreatment,
        source: defaultSource,
        purchase_price: 0,
        purchase_date: new Date().toISOString().split('T')[0],
        grading: '',
        notes: '',
        quantity: 1
    })

    // OpenSea URL state (for NFTs)
    const [openSeaUrl, setOpenSeaUrl] = useState('')
    const [openSeaParsed, setOpenSeaParsed] = useState<{ chain?: string; contract?: string; tokenId?: string; valid: boolean }>({ valid: false })

    // Parse OpenSea URL when it changes
    useEffect(() => {
        if (openSeaUrl) {
            const parsed = parseOpenSeaUrl(openSeaUrl)
            setOpenSeaParsed(parsed)
            if (parsed.valid && parsed.tokenId) {
                // Auto-populate notes with token details
                const tokenNote = `Token #${parsed.tokenId} on ${parsed.chain || 'ethereum'}`
                setForm(f => ({
                    ...f,
                    notes: f.notes ? `${tokenNote}\n${f.notes}` : tokenNote
                }))
            }
        } else {
            setOpenSeaParsed({ valid: false })
        }
    }, [openSeaUrl])

    // Update form defaults when product type changes
    useEffect(() => {
        setForm(f => ({
            ...f,
            treatment: treatmentOptions.includes(f.treatment) ? f.treatment : defaultTreatment,
            source: sourceOptions.includes(f.source) ? f.source : defaultSource
        }))
    }, [productType])

    // Update price when treatment changes or pricing data loads
    useEffect(() => {
        const suggestedPrice = getSuggestedPrice(form.treatment)
        setForm(f => ({ ...f, purchase_price: suggestedPrice }))
    }, [form.treatment, pricingData])

    // Initialize price when card changes
    useEffect(() => {
        const initialPrice = card.floor_price || card.latest_price || 0
        setForm(f => ({ ...f, purchase_price: initialPrice }))
        setOpenSeaUrl('')
    }, [card.id])

    // Split entry mode (multiple cards)
    const [splitMode, setSplitMode] = useState(false)
    const [splitCards, setSplitCards] = useState<PortfolioCardCreate[]>([])

    // Add single card mutation
    const addSingleMutation = useMutation({
        mutationFn: async (data: PortfolioCardCreate) => {
            return await api.post('portfolio/cards', { json: data }).json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['portfolio-cards'] })
            queryClient.invalidateQueries({ queryKey: ['portfolio-summary'] })
            onClose()
            resetForm()
        }
    })

    // Add batch mutation
    const addBatchMutation = useMutation({
        mutationFn: async (cards: PortfolioCardCreate[]) => {
            return await api.post('portfolio/cards/batch', { json: { cards } }).json()
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['portfolio-cards'] })
            queryClient.invalidateQueries({ queryKey: ['portfolio-summary'] })
            onClose()
            resetForm()
        }
    })

    const resetForm = () => {
        setForm({
            treatment: defaultTreatment,
            source: defaultSource,
            purchase_price: getSuggestedPrice(defaultTreatment),
            purchase_date: new Date().toISOString().split('T')[0],
            grading: '',
            notes: '',
            quantity: 1
        })
        setSplitCards([])
        setSplitMode(false)
        setOpenSeaUrl('')
    }

    const handleSubmitSingle = (e: React.FormEvent) => {
        e.preventDefault()
        addSingleMutation.mutate({
            card_id: card.id,
            treatment: form.treatment,
            source: form.source,
            purchase_price: form.purchase_price,
            purchase_date: form.purchase_date || null,
            grading: form.grading || null,
            notes: form.notes || null,
            quantity: form.quantity
        })
    }

    const handleSubmitBatch = () => {
        if (splitCards.length === 0) return
        addBatchMutation.mutate(splitCards)
    }

    const addSplitCard = () => {
        setSplitCards([...splitCards, {
            card_id: card.id,
            treatment: form.treatment,
            source: form.source,
            purchase_price: form.purchase_price,
            purchase_date: form.purchase_date || null,
            grading: form.grading || null,
            notes: form.notes || null,
            quantity: form.quantity
        }])
        // Reset only price and quantity for next entry (keep treatment/source)
        setForm({ ...form, purchase_price: getSuggestedPrice(form.treatment), grading: '', notes: '', quantity: 1 })
    }

    const removeSplitCard = (index: number) => {
        setSplitCards(splitCards.filter((_, i) => i !== index))
    }

    return (
        <>
            {/* Backdrop - z-[60] to be above nav */}
            {isOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-[60] backdrop-blur-sm"
                    onClick={onClose}
                />
            )}

            {/* Drawer - z-[70] to be above backdrop */}
            <div
                ref={containerRef}
                {...modalProps}
                aria-labelledby="portfolio-modal-title"
                className={clsx(
                    "fixed inset-y-0 right-0 w-full md:w-[420px] bg-card border-l border-border shadow-2xl transform transition-transform duration-300 ease-in-out z-[70] flex flex-col",
                    isOpen ? "translate-x-0" : "translate-x-full"
                )}
            >
                {/* Header with Card Image */}
                <div className="relative overflow-hidden border-b border-border">
                    {/* Card Image Background */}
                    {card.image_url && (
                        <div className="absolute inset-0">
                            <img
                                src={card.image_url}
                                alt=""
                                className="w-full h-full object-cover object-top opacity-30 blur-sm scale-110"
                            />
                            {/* Gradient Scrim */}
                            <div className="absolute inset-0 bg-gradient-to-b from-card/60 via-card/80 to-card" />
                        </div>
                    )}
                    {/* Header Content */}
                    <div className="relative flex items-center justify-between p-6">
                        <div className="flex items-center gap-3">
                            {card.image_url ? (
                                <img
                                    src={card.image_url}
                                    alt={card.name}
                                    className="w-12 h-16 object-cover rounded border border-border/50 shadow-lg"
                                />
                            ) : (
                                <Wallet className="w-5 h-5 text-primary" />
                            )}
                            <div>
                                <h2 id="portfolio-modal-title" className="text-lg font-bold uppercase tracking-tight">Add to Portfolio</h2>
                                <p className="text-xs text-muted-foreground">{card.name}</p>
                                <p className="text-[10px] text-muted-foreground">{card.set_name}</p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="text-muted-foreground hover:text-foreground transition-colors"
                        >
                            <XIcon size={20} />
                        </button>
                    </div>
                </div>

                {/* Mode Toggle */}
                <div className="px-6 pt-4 flex gap-2">
                    <button
                        type="button"
                        onClick={() => setSplitMode(false)}
                        className={clsx(
                            "flex-1 text-xs uppercase font-bold py-2 rounded transition-colors",
                            !splitMode ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80"
                        )}
                    >
                        Single Card
                    </button>
                    <button
                        type="button"
                        onClick={() => setSplitMode(true)}
                        className={clsx(
                            "flex-1 text-xs uppercase font-bold py-2 rounded transition-colors",
                            splitMode ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80"
                        )}
                    >
                        Multi Entry ({splitCards.length})
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmitSingle} className="flex-1 overflow-y-auto p-6 space-y-4">
                    {/* Treatment / Variant */}
                    <div>
                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                            {productType === 'Single' ? 'Treatment' : productType === 'NFT' ? 'Rarity' : 'Condition'}
                        </label>
                        <SimpleDropdown
                            value={form.treatment}
                            onChange={(value) => setForm({ ...form, treatment: value })}
                            options={treatmentOptions.map(t => ({ value: t, label: t }))}
                            triggerClassName="font-mono"
                        />
                    </div>

                    {/* Source / Marketplace */}
                    <div>
                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                            {isNFT ? 'Marketplace' : 'Where Purchased'}
                        </label>
                        <SimpleDropdown
                            value={form.source}
                            onChange={(value) => setForm({ ...form, source: value })}
                            options={sourceOptions.map(s => ({ value: s, label: s }))}
                            triggerClassName="font-mono"
                        />
                    </div>

                    {/* OpenSea URL (for NFTs when OpenSea is selected) */}
                    {isNFT && form.source === 'OpenSea' && (
                        <div>
                            <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                                OpenSea URL <span className="text-[10px] normal-case">(paste to auto-fill)</span>
                            </label>
                            <div className="relative">
                                <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <input
                                    type="url"
                                    placeholder="https://opensea.io/item/ethereum/0x.../123"
                                    value={openSeaUrl}
                                    onChange={(e) => setOpenSeaUrl(e.target.value)}
                                    className={clsx(
                                        "w-full pl-10 pr-4 py-2 bg-background border rounded font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary",
                                        openSeaUrl && !openSeaParsed.valid ? "border-red-500" : "border-border",
                                        openSeaParsed.valid ? "border-brand-300" : ""
                                    )}
                                />
                            </div>
                            {openSeaParsed.valid && (
                                <div className="text-[10px] text-brand-300 mt-1 flex items-center gap-1">
                                    <span>Token #{openSeaParsed.tokenId}</span>
                                    <span className="text-muted-foreground">on {openSeaParsed.chain}</span>
                                </div>
                            )}
                            {openSeaUrl && !openSeaParsed.valid && (
                                <p className="text-[10px] text-red-500 mt-1">Invalid OpenSea URL format</p>
                            )}
                        </div>
                    )}

                    {/* Purchase Price */}
                    <div>
                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                            Purchase Price
                        </label>
                        <div className="relative">
                            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground">$</span>
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                value={form.purchase_price}
                                onChange={(e) => setForm({ ...form, purchase_price: parseFloat(e.target.value) || 0 })}
                                className="w-full pl-8 pr-4 py-2 bg-background border border-border rounded font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                            />
                        </div>
                        {/* Treatment-specific pricing hints */}
                        {(() => {
                            const treatmentPricing = getTreatmentPricing(form.treatment)

                            // Has treatment-specific data - show it
                            if (treatmentPricing && treatmentPricing.sales_count > 0) {
                                return (
                                    <div className="text-[10px] text-muted-foreground mt-1 space-y-0.5">
                                        <p className="text-brand-300">
                                            {treatmentPricing.sales_count} {form.treatment} sale{treatmentPricing.sales_count !== 1 ? 's' : ''} found
                                        </p>
                                        {treatmentPricing.floor_price != null && (
                                            <p>Floor: <span className="font-mono font-bold">${treatmentPricing.floor_price.toFixed(2)}</span></p>
                                        )}
                                        {treatmentPricing.median_price != null && treatmentPricing.median_price !== treatmentPricing.floor_price && (
                                            <p>Median: <span className="font-mono">${treatmentPricing.median_price.toFixed(2)}</span></p>
                                        )}
                                        {treatmentPricing.min_price != null && treatmentPricing.max_price != null && treatmentPricing.min_price !== treatmentPricing.max_price && (
                                            <p>Range: <span className="font-mono">${treatmentPricing.min_price.toFixed(2)} - ${treatmentPricing.max_price.toFixed(2)}</span></p>
                                        )}
                                    </div>
                                )
                            }

                            // No treatment-specific data - show alternatives
                            const treatmentsWithSales = pricingData?.by_treatment?.filter(t => t.sales_count > 0) || []
                            const hasAlternatives = treatmentsWithSales.length > 0

                            return (
                                <div className="text-[10px] mt-1 space-y-1">
                                    <p className="text-amber-500">No {form.treatment} sales recorded yet</p>
                                    {hasAlternatives ? (
                                        <div className="text-muted-foreground">
                                            <p className="mb-1">Treatments with sales data:</p>
                                            {treatmentsWithSales.slice(0, 3).map(t => (
                                                <p key={t.treatment} className="pl-2">
                                                    • {t.treatment}: <span className="font-mono">${(t.floor_price || t.avg_price || 0).toFixed(2)}</span>
                                                    <span className="text-muted-foreground/60"> ({t.sales_count} sale{t.sales_count !== 1 ? 's' : ''})</span>
                                                </p>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="text-muted-foreground">
                                            {card.floor_price ? (
                                                <>Estimated: <span className="font-mono">${card.floor_price.toFixed(2)}</span> (card average)</>
                                            ) : (
                                                <>No pricing data available for this card</>
                                            )}
                                        </p>
                                    )}
                                </div>
                            )
                        })()}
                    </div>

                    {/* Purchase Date */}
                    <div>
                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                            Purchase Date
                        </label>
                        <input
                            type="date"
                            value={form.purchase_date}
                            onChange={(e) => setForm({ ...form, purchase_date: e.target.value })}
                            className="w-full px-4 py-2 bg-background border border-border rounded font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                        />
                    </div>

                    {/* Grading (optional) */}
                    <div>
                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                            Grading <span className="text-[10px] normal-case">(optional)</span>
                        </label>
                        <input
                            type="text"
                            placeholder="e.g., PSA 10, BGS 9.5"
                            value={form.grading}
                            onChange={(e) => setForm({ ...form, grading: e.target.value })}
                            className="w-full px-4 py-2 bg-background border border-border rounded font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                        />
                    </div>

                    {/* Notes (optional) */}
                    <div>
                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                            Notes <span className="text-[10px] normal-case">(optional)</span>
                        </label>
                        <textarea
                            rows={2}
                            placeholder="Any notes about this card..."
                            value={form.notes}
                            onChange={(e) => setForm({ ...form, notes: e.target.value })}
                            className="w-full px-4 py-2 bg-background border border-border rounded font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                        />
                    </div>

                    {/* Quantity */}
                    <div>
                        <label className="block text-xs uppercase font-bold text-muted-foreground mb-2">
                            Quantity
                        </label>
                        <div className="flex items-center gap-3">
                            <button
                                type="button"
                                onClick={() => setForm({ ...form, quantity: Math.max(1, form.quantity - 1) })}
                                className="w-10 h-10 flex items-center justify-center bg-muted hover:bg-muted/80 rounded transition-colors"
                                disabled={form.quantity <= 1}
                            >
                                <Minus className="w-4 h-4" />
                            </button>
                            <input
                                type="number"
                                min="1"
                                max="100"
                                value={form.quantity}
                                onChange={(e) => setForm({ ...form, quantity: Math.max(1, Math.min(100, parseInt(e.target.value) || 1)) })}
                                className="w-20 px-4 py-2 bg-background border border-border rounded font-mono text-sm text-center focus:outline-none focus:ring-2 focus:ring-primary"
                            />
                            <button
                                type="button"
                                onClick={() => setForm({ ...form, quantity: Math.min(100, form.quantity + 1) })}
                                className="w-10 h-10 flex items-center justify-center bg-muted hover:bg-muted/80 rounded transition-colors"
                                disabled={form.quantity >= 100}
                            >
                                <PlusIcon size={16} />
                            </button>
                            {form.quantity > 1 && (
                                <span className="text-xs text-muted-foreground">
                                    Total: <span className="font-mono font-bold">${(form.purchase_price * form.quantity).toFixed(2)}</span>
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Split Mode: Added Cards List */}
                    {splitMode && splitCards.length > 0 && (
                        <div className="border border-border rounded p-4 bg-muted/10">
                            <div className="text-xs uppercase font-bold text-muted-foreground mb-3">
                                Cards to Add ({splitCards.reduce((acc, sc) => acc + (sc.quantity || 1), 0)} total)
                            </div>
                            <div className="space-y-2 max-h-40 overflow-y-auto">
                                {splitCards.map((sc, idx) => (
                                    <div key={idx} className="flex items-center justify-between text-xs bg-background p-2 rounded border border-border/50">
                                        <div className="flex items-center gap-2">
                                            {(sc.quantity || 1) > 1 && (
                                                <span className="bg-primary/20 text-primary px-1.5 py-0.5 rounded text-[10px] font-bold">x{sc.quantity}</span>
                                            )}
                                            <span className="font-mono">${sc.purchase_price.toFixed(2)}</span>
                                            <span className="text-muted-foreground">{sc.treatment}</span>
                                            {sc.grading && <span className="text-amber-500">{sc.grading}</span>}
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => removeSplitCard(idx)}
                                            className="text-red-500 hover:text-red-400"
                                        >
                                            <Minus className="w-3 h-3" />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Error Display */}
                    {(addSingleMutation.isError || addBatchMutation.isError) && (
                        <div className="text-xs text-red-500 text-center p-3 bg-red-500/10 rounded border border-red-500/20">
                            Failed to add card. Please try again or check if you're logged in.
                        </div>
                    )}
                </form>

                {/* Actions - Fixed at bottom */}
                <div className="p-6 border-t border-border bg-card">
                    <div className="flex gap-3">
                        {splitMode ? (
                            <>
                                <button
                                    type="button"
                                    onClick={addSplitCard}
                                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 border border-primary text-primary rounded text-sm uppercase font-bold hover:bg-primary/10 transition-colors"
                                >
                                    <PlusIcon size={16} /> Add {form.quantity > 1 ? `${form.quantity} Cards` : 'Card'}
                                </button>
                                <button
                                    type="button"
                                    onClick={handleSubmitBatch}
                                    disabled={splitCards.length === 0 || addBatchMutation.isPending}
                                    className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded text-sm uppercase font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
                                >
                                    {addBatchMutation.isPending ? 'Saving...' : (() => {
                                        const totalCards = splitCards.reduce((acc, sc) => acc + (sc.quantity || 1), 0)
                                        return `Save ${totalCards} Card${totalCards !== 1 ? 's' : ''}`
                                    })()}
                                </button>
                            </>
                        ) : (
                            <>
                                <button
                                    type="button"
                                    onClick={onClose}
                                    className="flex-1 px-4 py-2 border border-border rounded text-sm uppercase font-bold hover:bg-muted/50 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="button"
                                    onClick={handleSubmitSingle}
                                    disabled={addSingleMutation.isPending}
                                    className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded text-sm uppercase font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
                                >
                                    {addSingleMutation.isPending ? 'Adding...' : form.quantity > 1 ? `Add ${form.quantity} Cards` : 'Add to Portfolio'}
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </>
    )
}
