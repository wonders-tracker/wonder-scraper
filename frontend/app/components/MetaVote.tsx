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
    <div className="border-l border-border pl-8">
      <div className="text-[10px] text-muted-foreground uppercase mb-1 tracking-wider">Is Meta?</div>

      {/* Vote counts */}
      <div className="flex items-center gap-3 mb-2">
        <span className="text-sm font-mono">
          <span className="text-brand-300">{summary.yes}</span>
          <span className="text-muted-foreground mx-1">Y</span>
        </span>
        <span className="text-sm font-mono">
          <span className="text-red-500">{summary.no}</span>
          <span className="text-muted-foreground mx-1">N</span>
        </span>
        <span className="text-sm font-mono">
          <span className="text-amber-500">{summary.unsure}</span>
          <span className="text-muted-foreground mx-1">?</span>
        </span>
      </div>

      {/* Vote buttons or login prompt */}
      {isLoggedIn ? (
        <div className="flex items-center gap-1">
          <button
            onClick={() => handleVote('yes')}
            disabled={voteMutation.isPending || removeMutation.isPending}
            className={`px-2 py-1 rounded text-[10px] uppercase font-bold transition-colors ${
              userVote === 'yes'
                ? 'bg-brand-400 text-white'
                : 'bg-muted hover:bg-brand-400/20 text-muted-foreground hover:text-brand-300'
            }`}
          >
            <ThumbsUp className="w-3 h-3 inline mr-1" />
            Yes
          </button>
          <button
            onClick={() => handleVote('no')}
            disabled={voteMutation.isPending || removeMutation.isPending}
            className={`px-2 py-1 rounded text-[10px] uppercase font-bold transition-colors ${
              userVote === 'no'
                ? 'bg-red-600 text-white'
                : 'bg-muted hover:bg-red-600/20 text-muted-foreground hover:text-red-400'
            }`}
          >
            <ThumbsDown className="w-3 h-3 inline mr-1" />
            No
          </button>
          <button
            onClick={() => handleVote('unsure')}
            disabled={voteMutation.isPending || removeMutation.isPending}
            className={`px-2 py-1 rounded text-[10px] uppercase font-bold transition-colors ${
              userVote === 'unsure'
                ? 'bg-amber-600 text-white'
                : 'bg-muted hover:bg-amber-600/20 text-muted-foreground hover:text-amber-400'
            }`}
          >
            <HelpCircle className="w-3 h-3 inline mr-1" />
            ?
          </button>
        </div>
      ) : (
        <Link
          to="/login"
          className="flex items-center gap-1.5 px-2 py-1 bg-[#5865F2] text-white rounded text-[10px] uppercase font-bold hover:bg-[#4752C4] transition-colors w-fit"
        >
          <DiscordIcon className="w-3 h-3" />
          Sign in to vote
        </Link>
      )}
    </div>
  )
}
