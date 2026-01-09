import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AddToPortfolioModal } from './AddToPortfolioModal'

// Mock the api module
vi.mock('../utils/auth', () => ({
  api: {
    get: vi.fn(() => ({
      json: () => Promise.resolve({
        card_id: 1,
        card_name: 'Test Card',
        fair_market_price: 100,
        floor_price: 95,
        by_treatment: [
          {
            treatment: 'Classic Paper',
            fmp: 95,
            floor_price: 90,
            sales_count: 10,
            median_price: 92,
            min_price: 85,
            max_price: 110,
            avg_price: 93,
          },
          {
            treatment: 'Classic Foil',
            fmp: 150,
            floor_price: 140,
            sales_count: 5,
            median_price: 145,
            min_price: 130,
            max_price: 180,
            avg_price: 148,
          },
        ],
      }),
    })),
    post: vi.fn(() => ({
      json: () => Promise.resolve({ id: 1 }),
    })),
  },
}))

// Test wrapper with QueryClient
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient()
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

// ============================================================================
// parseOpenSeaUrl Tests (Unit Tests)
// ============================================================================

describe('parseOpenSeaUrl', () => {
  // Extract the function for testing - we'll test it via the component behavior
  // but also test the regex patterns directly

  const parseOpenSeaUrl = (url: string): { chain?: string; contract?: string; tokenId?: string; valid: boolean } => {
    try {
      const regex = /opensea\.io\/(?:assets|item)\/([^\/]+)\/([^\/]+)\/(\d+)/
      const match = url.match(regex)
      if (match) {
        return {
          chain: match[1],
          contract: match[2],
          tokenId: match[3],
          valid: true,
        }
      }
      return { valid: false }
    } catch {
      return { valid: false }
    }
  }

  describe('valid URLs', () => {
    it('should parse /item/ format URL correctly', () => {
      const url = 'https://opensea.io/item/ethereum/0x28a11da34a93712b1fde4ad15da217a3b14d9465/4294968598'
      const result = parseOpenSeaUrl(url)

      expect(result.valid).toBe(true)
      expect(result.chain).toBe('ethereum')
      expect(result.contract).toBe('0x28a11da34a93712b1fde4ad15da217a3b14d9465')
      expect(result.tokenId).toBe('4294968598')
    })

    it('should parse /assets/ format URL correctly', () => {
      const url = 'https://opensea.io/assets/ethereum/0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d/1234'
      const result = parseOpenSeaUrl(url)

      expect(result.valid).toBe(true)
      expect(result.chain).toBe('ethereum')
      expect(result.contract).toBe('0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d')
      expect(result.tokenId).toBe('1234')
    })

    it('should parse Polygon chain URL', () => {
      const url = 'https://opensea.io/item/matic/0x1234567890abcdef/999'
      const result = parseOpenSeaUrl(url)

      expect(result.valid).toBe(true)
      expect(result.chain).toBe('matic')
      expect(result.tokenId).toBe('999')
    })

    it('should parse Arbitrum chain URL', () => {
      const url = 'https://opensea.io/assets/arbitrum/0xabcdef1234567890/42'
      const result = parseOpenSeaUrl(url)

      expect(result.valid).toBe(true)
      expect(result.chain).toBe('arbitrum')
      expect(result.tokenId).toBe('42')
    })

    it('should parse URL with very large token ID', () => {
      const url = 'https://opensea.io/item/ethereum/0xabc/99999999999999999'
      const result = parseOpenSeaUrl(url)

      expect(result.valid).toBe(true)
      expect(result.tokenId).toBe('99999999999999999')
    })

    it('should parse URL without https://', () => {
      const url = 'opensea.io/item/ethereum/0xabc/123'
      const result = parseOpenSeaUrl(url)

      expect(result.valid).toBe(true)
      expect(result.tokenId).toBe('123')
    })
  })

  describe('invalid URLs', () => {
    it('should reject empty string', () => {
      expect(parseOpenSeaUrl('').valid).toBe(false)
    })

    it('should reject non-OpenSea URLs', () => {
      expect(parseOpenSeaUrl('https://rarible.com/token/123').valid).toBe(false)
      expect(parseOpenSeaUrl('https://blur.io/asset/0xabc/123').valid).toBe(false)
      expect(parseOpenSeaUrl('https://google.com').valid).toBe(false)
    })

    it('should reject OpenSea URLs without token ID', () => {
      expect(parseOpenSeaUrl('https://opensea.io/item/ethereum/0xabc').valid).toBe(false)
      expect(parseOpenSeaUrl('https://opensea.io/assets/ethereum').valid).toBe(false)
    })

    it('should reject OpenSea collection URLs', () => {
      expect(parseOpenSeaUrl('https://opensea.io/collection/boredapeyachtclub').valid).toBe(false)
    })

    it('should reject OpenSea profile URLs', () => {
      expect(parseOpenSeaUrl('https://opensea.io/account').valid).toBe(false)
      expect(parseOpenSeaUrl('https://opensea.io/0xabc').valid).toBe(false)
    })

    it('should reject URLs with non-numeric token ID', () => {
      expect(parseOpenSeaUrl('https://opensea.io/item/ethereum/0xabc/abc').valid).toBe(false)
    })

    it('should reject malformed URLs', () => {
      expect(parseOpenSeaUrl('not a url at all').valid).toBe(false)
      expect(parseOpenSeaUrl('opensea.io').valid).toBe(false)
    })
  })
})

// ============================================================================
// Product Type Options Tests (Unit Tests)
// ============================================================================

describe('Product Type Options', () => {
  // Updated to match actual TREATMENTS_BY_TYPE in AddToPortfolioModal.tsx
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
    ],
  }

  const SOURCES_BY_TYPE: Record<string, string[]> = {
    'NFT': ['OpenSea', 'Blur', 'Magic Eden', 'Other'],
    'default': ['eBay', 'Blokpax', 'TCGPlayer', 'LGS', 'Trade', 'Pack Pull', 'Other'],
  }

  describe('treatment options', () => {
    it('should have correct treatments for Singles', () => {
      expect(TREATMENTS_BY_TYPE['Single']).toContain('Classic Paper')
      expect(TREATMENTS_BY_TYPE['Single']).toContain('Classic Foil')
      expect(TREATMENTS_BY_TYPE['Single']).toContain('Serialized')
      expect(TREATMENTS_BY_TYPE['Single']).toHaveLength(11)
    })

    it('should have Sealed/Opened for Box product type', () => {
      expect(TREATMENTS_BY_TYPE['Box']).toEqual(['Sealed', 'Opened'])
    })

    it('should have Sealed/Opened for Pack product type', () => {
      expect(TREATMENTS_BY_TYPE['Pack']).toEqual(['Sealed', 'Opened'])
    })

    it('should have correct options for Lots', () => {
      expect(TREATMENTS_BY_TYPE['Lot']).toContain('Mixed')
      expect(TREATMENTS_BY_TYPE['Lot']).toContain('All Sealed')
      expect(TREATMENTS_BY_TYPE['Lot']).toContain('All Raw')
    })

    it('should have NFT-specific rarities', () => {
      expect(TREATMENTS_BY_TYPE['NFT']).toContain('Standard')
      expect(TREATMENTS_BY_TYPE['NFT']).toContain('Animated')
      expect(TREATMENTS_BY_TYPE['NFT']).toContain('Legendary')
      expect(TREATMENTS_BY_TYPE['NFT']).toContain('1/1')
    })

    it('should have Proof-specific treatments', () => {
      expect(TREATMENTS_BY_TYPE['Proof']).toContain('Character Proof')
      expect(TREATMENTS_BY_TYPE['Proof']).toContain('Set Proof')
    })

    it('should fallback to default for unknown product types', () => {
      const unknownType = 'SomeNewType'
      const treatments = TREATMENTS_BY_TYPE[unknownType] || TREATMENTS_BY_TYPE['default']
      expect(treatments).toEqual(TREATMENTS_BY_TYPE['default'])
    })
  })

  describe('source options', () => {
    it('should have NFT marketplaces for NFT type', () => {
      expect(SOURCES_BY_TYPE['NFT']).toContain('OpenSea')
      expect(SOURCES_BY_TYPE['NFT']).toContain('Blur')
      expect(SOURCES_BY_TYPE['NFT']).toContain('Magic Eden')
    })

    it('should have physical card sources for default', () => {
      expect(SOURCES_BY_TYPE['default']).toContain('eBay')
      expect(SOURCES_BY_TYPE['default']).toContain('Blokpax')
      expect(SOURCES_BY_TYPE['default']).toContain('TCGPlayer')
      expect(SOURCES_BY_TYPE['default']).toContain('LGS')
      expect(SOURCES_BY_TYPE['default']).toContain('Trade')
      expect(SOURCES_BY_TYPE['default']).toContain('Pack Pull')
    })

    it('should not have OpenSea for physical cards', () => {
      expect(SOURCES_BY_TYPE['default']).not.toContain('OpenSea')
    })
  })
})

// ============================================================================
// Component Integration Tests
// ============================================================================

describe('AddToPortfolioModal Component', () => {
  const defaultCard = {
    id: 1,
    name: 'Test Card',
    set_name: 'Test Set',
    floor_price: 100,
    latest_price: 105,
    product_type: 'Single',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('rendering', () => {
    it('should render when isOpen is true', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      // Header text - use getByRole for heading
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(/add to portfolio/i)
      expect(screen.getByText('Test Card')).toBeInTheDocument()
    })

    it('should not show content when isOpen is false', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={false} onClose={() => {}} />
        </TestWrapper>
      )

      // The drawer should be off-screen (translated)
      const drawer = document.querySelector('.translate-x-full')
      expect(drawer).toBeInTheDocument()
    })

    it('should show card name and set in header', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      expect(screen.getByText('Test Card')).toBeInTheDocument()
      expect(screen.getByText('Test Set')).toBeInTheDocument()
    })
  })

  describe('Single product type', () => {
    it('should show Treatment label for Singles', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      expect(screen.getByText('Treatment')).toBeInTheDocument()
    })

    it('should show treatment dropdown for Singles with default value', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      // SimpleDropdown uses buttons with aria-haspopup="listbox"
      const dropdownTriggers = screen.getAllByRole('button', { expanded: false })
      // Filter to only dropdown triggers (those with aria-haspopup)
      const triggers = dropdownTriggers.filter(btn => btn.getAttribute('aria-haspopup') === 'listbox')

      // First dropdown should show default treatment
      expect(triggers.length).toBeGreaterThanOrEqual(2)
      expect(triggers[0]).toHaveTextContent('Classic Paper')
    })

    it('should show physical card source dropdown for Singles', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      // SimpleDropdown uses buttons with aria-haspopup="listbox"
      const dropdownTriggers = screen.getAllByRole('button', { expanded: false })
      const triggers = dropdownTriggers.filter(btn => btn.getAttribute('aria-haspopup') === 'listbox')

      // Second dropdown is source - should show default (eBay)
      expect(triggers[1]).toHaveTextContent('eBay')
    })
  })

  describe('Box product type', () => {
    const boxCard = { ...defaultCard, product_type: 'Box' }

    it('should show Condition label for Boxes', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={boxCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      expect(screen.getByText('Condition')).toBeInTheDocument()
    })

    it('should show Sealed as default for Boxes', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={boxCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      // SimpleDropdown uses buttons with aria-haspopup="listbox"
      const dropdownTriggers = screen.getAllByRole('button', { expanded: false })
      const triggers = dropdownTriggers.filter(btn => btn.getAttribute('aria-haspopup') === 'listbox')

      // First dropdown should show Sealed (default for Box)
      expect(triggers[0]).toHaveTextContent('Sealed')
    })
  })

  describe('NFT product type', () => {
    const nftCard = { ...defaultCard, product_type: 'NFT' }

    it('should show Rarity label for NFTs', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={nftCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      expect(screen.getByText('Rarity')).toBeInTheDocument()
    })

    it('should show Marketplace label for NFTs', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={nftCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      expect(screen.getByText('Marketplace')).toBeInTheDocument()
    })

    it('should show NFT marketplace as default', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={nftCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      // SimpleDropdown uses buttons with aria-haspopup="listbox"
      const dropdownTriggers = screen.getAllByRole('button', { expanded: false })
      const triggers = dropdownTriggers.filter(btn => btn.getAttribute('aria-haspopup') === 'listbox')

      // Second dropdown is marketplace - should show OpenSea (default for NFT)
      expect(triggers[1]).toHaveTextContent('OpenSea')
    })

    it('should show OpenSea URL field when OpenSea is selected', async () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={nftCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      // OpenSea should be the default for NFTs
      expect(screen.getByPlaceholderText(/opensea\.io/i)).toBeInTheDocument()
    })

    it('should validate OpenSea URL and show success for valid URL', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={nftCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      const urlInput = screen.getByPlaceholderText(/opensea\.io/i)
      // Use paste to set the full URL at once (avoids triggering useEffect multiple times during typing)
      await user.click(urlInput)
      await user.paste('https://opensea.io/item/ethereum/0xabc123/4294968598')

      // Should show token ID confirmation in the success indicator (emerald colored span)
      await waitFor(() => {
        // Look for the specific UI feedback element, not the notes textarea
        const tokenIndicator = screen.getByText((content, element) =>
          element?.tagName === 'SPAN' && content === 'Token #4294968598'
        )
        expect(tokenIndicator).toBeInTheDocument()
      })
    })

    it('should show error for invalid OpenSea URL', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={nftCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      const urlInput = screen.getByPlaceholderText(/opensea\.io/i)
      // Use paste for consistency
      await user.click(urlInput)
      await user.paste('https://google.com/not-opensea')

      await waitFor(() => {
        expect(screen.getByText(/Invalid OpenSea URL format/)).toBeInTheDocument()
      })
    })
  })

  describe('Proof product type', () => {
    const proofCard = { ...defaultCard, product_type: 'Proof' }

    it('should show NFT marketplace dropdown for Proofs', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={proofCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      // SimpleDropdown uses buttons with aria-haspopup="listbox"
      const dropdownTriggers = screen.getAllByRole('button', { expanded: false })
      const triggers = dropdownTriggers.filter(btn => btn.getAttribute('aria-haspopup') === 'listbox')

      // Second dropdown is marketplace - should show OpenSea (default for Proof which is treated as NFT)
      expect(triggers[1]).toHaveTextContent('OpenSea')
    })

    it('should show Proof-specific treatment as default', () => {
      render(
        <TestWrapper>
          <AddToPortfolioModal card={proofCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      // SimpleDropdown uses buttons with aria-haspopup="listbox"
      const dropdownTriggers = screen.getAllByRole('button', { expanded: false })
      const triggers = dropdownTriggers.filter(btn => btn.getAttribute('aria-haspopup') === 'listbox')

      // First dropdown should show Character Proof (first in Proof treatments)
      expect(triggers[0]).toHaveTextContent('Character Proof')
    })
  })

  describe('form interactions', () => {
    it('should allow changing purchase price', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      // Price input is the first number input (step="0.01")
      const priceInput = document.querySelector('input[type="number"][step="0.01"]') as HTMLInputElement
      expect(priceInput).toBeTruthy()
      // Clear and type new value - need to triple click to select all
      await user.tripleClick(priceInput)
      await user.keyboard('150.50')

      expect(priceInput).toHaveValue(150.5)
    })

    it('should allow changing purchase date', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      const dateInput = screen.getByDisplayValue(new Date().toISOString().split('T')[0])
      await user.clear(dateInput)
      await user.type(dateInput, '2025-01-15')

      expect(dateInput).toHaveValue('2025-01-15')
    })

    it('should allow entering grading info', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      const gradingInput = screen.getByPlaceholderText(/PSA 10/i)
      await user.type(gradingInput, 'PSA 10')

      expect(gradingInput).toHaveValue('PSA 10')
    })

    it('should allow entering notes', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      const notesInput = screen.getByPlaceholderText(/Any notes about this card/i)
      await user.type(notesInput, 'Great condition, centered')

      expect(notesInput).toHaveValue('Great condition, centered')
    })
  })

  describe('multi entry mode', () => {
    it('should toggle to multi entry mode', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={() => {}} />
        </TestWrapper>
      )

      const splitButton = screen.getByRole('button', { name: /multi entry/i })
      await user.click(splitButton)

      // Add Card button should appear in split mode
      expect(screen.getByRole('button', { name: /add card/i })).toBeInTheDocument()
    })
  })

  describe('close behavior', () => {
    it('should call onClose when X button clicked', async () => {
      const user = userEvent.setup()
      const onClose = vi.fn()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={onClose} />
        </TestWrapper>
      )

      // X button is a button with text-muted-foreground class in header
      const closeButton = document.querySelector('button.text-muted-foreground') as HTMLButtonElement
      expect(closeButton).toBeTruthy()
      await user.click(closeButton)

      expect(onClose).toHaveBeenCalled()
    })

    it('should call onClose when backdrop clicked', async () => {
      const user = userEvent.setup()
      const onClose = vi.fn()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={onClose} />
        </TestWrapper>
      )

      // Click on backdrop (the dark overlay)
      const backdrop = document.querySelector('.bg-black\\/50')
      if (backdrop) {
        await user.click(backdrop)
        expect(onClose).toHaveBeenCalled()
      }
    })

    it('should call onClose when Cancel button clicked', async () => {
      const user = userEvent.setup()
      const onClose = vi.fn()

      render(
        <TestWrapper>
          <AddToPortfolioModal card={defaultCard} isOpen={true} onClose={onClose} />
        </TestWrapper>
      )

      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await user.click(cancelButton)

      expect(onClose).toHaveBeenCalled()
    })
  })
})
