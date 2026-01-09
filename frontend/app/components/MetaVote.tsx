import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../utils/auth'
import { ThumbsUp, ThumbsDown, HelpCircle } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { DiscordIcon } from './icons/DiscordIcon'
import { useCurrentUser } from '../context/UserContext'

type MetaVoteSummary = {
  yes: number
  no: number
  unsure: number
  total: number
}

type MetaVoteResponse = {
  summary: MetaVoteSummary
  user_vote: string | null
  consensus: string | null
}

type MetaVoteProps = {
  cardId: number
}

export function MetaVote({ cardId }: MetaVoteProps) {
  const { user } = useCurrentUser()
  const isLoggedIn = !!user
  const queryClient = useQueryClient()

  // Fetch current vote data
  const { data: voteData, isLoading } = useQuery({
    queryKey: ['meta-vote', cardId],
    queryFn: () => api.get(`cards/${cardId}/meta`).json<MetaVoteResponse>(),
    staleTime: 30 * 1000, // 30 seconds
  })

  // Mutation to cast vote
  const voteMutation = useMutation({
    mutationFn: (vote: string) =>
      api.post(`cards/${cardId}/meta`, { json: { vote } }).json<MetaVoteResponse>(),
    onSuccess: (data) => {
      queryClient.setQueryData(['meta-vote', cardId], data)
    },
  })

  // Mutation to remove vote
  const removeMutation = useMutation({
    mutationFn: () => api.delete(`cards/${cardId}/meta`).json<MetaVoteResponse>(),
    onSuccess: (data) => {
      queryClient.setQueryData(['meta-vote', cardId], data)
    },
  })

  const handleVote = (vote: string) => {
    if (!isLoggedIn) return

    // If clicking the same vote, remove it
    if (voteData?.user_vote === vote) {
      removeMutation.mutate()
    } else {
      voteMutation.mutate(vote)
    }
  }

  const summary = voteData?.summary || { yes: 0, no: 0, unsure: 0, total: 0 }
  const userVote = voteData?.user_vote

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Label */}
      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Meta?</span>

      {/* Vote counts - compact */}
      <div className="flex items-center gap-2 text-xs font-mono">
        <span><span className="text-brand-300">{summary.yes}</span><span className="text-muted-foreground">Y</span></span>
        <span><span className="text-red-500">{summary.no}</span><span className="text-muted-foreground">N</span></span>
        <span><span className="text-amber-500">{summary.unsure}</span><span className="text-muted-foreground">?</span></span>
      </div>

      {/* Vote buttons - inline */}
      {isLoggedIn ? (
        <div className="flex items-center gap-1">
          <button
            onClick={() => handleVote('yes')}
            disabled={voteMutation.isPending || removeMutation.isPending}
            className={`p-1.5 rounded transition-colors ${
              userVote === 'yes'
                ? 'bg-brand-400 text-white'
                : 'bg-muted hover:bg-brand-400/20 text-muted-foreground hover:text-brand-300'
            }`}
            title="Yes, meta"
          >
            <ThumbsUp className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handleVote('no')}
            disabled={voteMutation.isPending || removeMutation.isPending}
            className={`p-1.5 rounded transition-colors ${
              userVote === 'no'
                ? 'bg-red-600 text-white'
                : 'bg-muted hover:bg-red-600/20 text-muted-foreground hover:text-red-400'
            }`}
            title="No, not meta"
          >
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handleVote('unsure')}
            disabled={voteMutation.isPending || removeMutation.isPending}
            className={`p-1.5 rounded transition-colors ${
              userVote === 'unsure'
                ? 'bg-amber-600 text-white'
                : 'bg-muted hover:bg-amber-600/20 text-muted-foreground hover:text-amber-400'
            }`}
            title="Unsure"
          >
            <HelpCircle className="w-3.5 h-3.5" />
          </button>
        </div>
      ) : (
        <Link
          to="/login"
          className="flex items-center gap-1 px-2 py-1 bg-[#5865F2] text-white rounded text-[10px] uppercase font-bold hover:bg-[#4752C4] transition-colors"
        >
          <DiscordIcon className="w-3 h-3" />
          Vote
        </Link>
      )}
    </div>
  )
}
