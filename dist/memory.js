                                         
                                        
import { stableHash } from "./canonical.js";

export const MACRO_MEMORY_ENTRY_SCHEMA = "trwm.macro_memory_entry.v1";
export const MACRO_MEMORY_SNAPSHOT_SCHEMA = "trwm.macro_memory_snapshot.v1";

                                                   
                        
                  
                
                     
                        
                            
                              
                         
                        
                            
                
                            
                    
 

                                                      
                        
                             
                       
                       
                                         
                       
 

                                   
                  
                
                     
                        
                            
                              
                         
                        
                            
 

export class BoundedMacroMemory                 {
  capacityPerContext        ;
  stalenessPenalty        ;
  totalUpdates = 0;
  evictedCount = 0;
          entries = new Map                                 ();

  constructor(capacityPerContext = 16, options                                = {}) {
    if (!Number.isInteger(capacityPerContext) || capacityPerContext <= 0) {
      throw new RangeError("capacityPerContext must be a positive integer");
    }
    const stalenessPenalty = options.stalenessPenalty ?? 0;
    if (!Number.isInteger(stalenessPenalty) || stalenessPenalty < 0) {
      throw new RangeError("stalenessPenalty must be a non-negative integer");
    }
    this.capacityPerContext = capacityPerContext;
    this.stalenessPenalty = stalenessPenalty;
  }

  async update(receipt         )                {
    const payload = receiptPayload(receipt);
    const macroSteps = macroStepsFromPayload      (payload);
    if (macroSteps.length === 0) {
      return;
    }
    this.totalUpdates += 1;
    const context = String(payload.context ?? "global");
    const token = await macroToken(macroSteps);
    const key = entryKey(context, token);
    let entry = this.entries.get(key);
    if (!entry) {
      entry = {
        context,
        token,
        macroSteps,
        acceptedCount: 0,
        prefixRejectCount: 0,
        terminalRejectCount: 0,
        firstSeenIndex: this.totalUpdates,
        lastSeenIndex: this.totalUpdates,
        latestReceiptHash: "",
      };
      this.entries.set(key, entry);
    }
    entry.lastSeenIndex = this.totalUpdates;
    entry.latestReceiptHash = receipt.receiptHash;
    if (receipt.committed && receipt.hardResult.result === "accept") {
      entry.acceptedCount += 1;
    } else if (receipt.commitDecision === "prefix_unsafe") {
      entry.prefixRejectCount += 1;
    } else if (receipt.hardResult.result === "reject") {
      entry.terminalRejectCount += 1;
    }
    this.evictOverCapacity(context);
  }

  async score(context        , macro             )                  {
    const entry = this.entries.get(entryKey(context, await macroToken(macro.steps)));
    return entry ? entryScore(entry) : 0;
  }

  async rank(context        , macros                    )                              {
    const rows = await Promise.all(macros.map(async (macro, idx) => ({
      macro,
      idx,
      entry: this.entries.get(entryKey(context, await macroToken(macro.steps))),
    })));
    return rows
      .sort((a, b) => {
        const aScore = a.entry ? entryScore(a.entry) : 0;
        const bScore = b.entry ? entryScore(b.entry) : 0;
        if (aScore !== bScore) {
          return bScore - aScore;
        }
        const aAccepted = a.entry?.acceptedCount ?? 0;
        const bAccepted = b.entry?.acceptedCount ?? 0;
        if (aAccepted !== bAccepted) {
          return bAccepted - aAccepted;
        }
        const aRejects = (a.entry?.prefixRejectCount ?? 0) + (a.entry?.terminalRejectCount ?? 0);
        const bRejects = (b.entry?.prefixRejectCount ?? 0) + (b.entry?.terminalRejectCount ?? 0);
        if (aRejects !== bRejects) {
          return aRejects - bRejects;
        }
        return a.idx - b.idx;
      })
      .map((row) => row.macro);
  }

  async snapshot()                                     {
    const entries = await Promise.all(
      Array.from(this.entries.values())
        .sort((a, b) => a.context < b.context ? -1 : a.context > b.context ? 1 : a.token < b.token ? -1 : a.token > b.token ? 1 : 0)
        .map((entry) => macroMemoryEntrySnapshot(entry, this.totalUpdates, this.stalenessPenalty)),
    );
    const snapshot                            = {
      schemaVersion: MACRO_MEMORY_SNAPSHOT_SCHEMA,
      capacityPerContext: this.capacityPerContext,
      totalUpdates: this.totalUpdates,
      evictedCount: this.evictedCount,
      entries,
      snapshotHash: "",
    };
    return { ...snapshot, snapshotHash: await macroMemorySnapshotHash(snapshot) };
  }

          evictOverCapacity(context        )       {
    let rows = Array.from(this.entries.values()).filter((entry) => entry.context === context);
    while (rows.length > this.capacityPerContext) {
      rows.sort((a, b) => {
        const aPriority = retentionPriority(a, this.totalUpdates, this.stalenessPenalty);
        const bPriority = retentionPriority(b, this.totalUpdates, this.stalenessPenalty);
        if (aPriority !== bPriority) return aPriority - bPriority;
        if (a.acceptedCount !== b.acceptedCount) return a.acceptedCount - b.acceptedCount;
        const aRejects = a.prefixRejectCount + a.terminalRejectCount;
        const bRejects = b.prefixRejectCount + b.terminalRejectCount;
        if (aRejects !== bRejects) return bRejects - aRejects;
        if (a.lastSeenIndex !== b.lastSeenIndex) return b.lastSeenIndex - a.lastSeenIndex;
        return a.token < b.token ? -1 : a.token > b.token ? 1 : 0;
      });
      const victim = rows[0];
      this.entries.delete(entryKey(victim.context, victim.token));
      this.evictedCount += 1;
      rows = Array.from(this.entries.values()).filter((entry) => entry.context === context);
    }
  }
}

export async function macroToken(steps           )                  {
  return stableHash(steps);
}

export async function macroMemoryEntryHash(entry                                            )                  {
  const { entryHash: _entryHash, ...withoutHash } = entry                           ;
  return stableHash(withoutHash);
}

export async function macroMemorySnapshotHash(snapshot                                               )                  {
  const { snapshotHash: _snapshotHash, ...withoutHash } = snapshot                           ;
  return stableHash(withoutHash);
}

export async function validateMacroMemorySnapshot(snapshot                                               )                   {
  try {
    if (!isRecord(snapshot) || snapshot.schemaVersion !== MACRO_MEMORY_SNAPSHOT_SCHEMA) {
      return false;
    }
    if (!Number.isInteger(snapshot.capacityPerContext) || Number(snapshot.capacityPerContext) <= 0) {
      return false;
    }
    if (!Array.isArray(snapshot.entries)) {
      return false;
    }
    for (const entry of snapshot.entries) {
      if (!isRecord(entry) || entry.schemaVersion !== MACRO_MEMORY_ENTRY_SCHEMA) {
        return false;
      }
      if (entry.entryHash !== await macroMemoryEntryHash(entry)) {
        return false;
      }
    }
    return snapshot.snapshotHash === await macroMemorySnapshotHash(snapshot);
  } catch {
    return false;
  }
}

async function macroMemoryEntrySnapshot      (
  entry                         ,
  currentIndex        ,
  stalenessPenalty        ,
)                                  {
  const snapshot                         = {
    schemaVersion: MACRO_MEMORY_ENTRY_SCHEMA,
    context: entry.context,
    token: entry.token,
    macroSteps: entry.macroSteps,
    acceptedCount: entry.acceptedCount,
    prefixRejectCount: entry.prefixRejectCount,
    terminalRejectCount: entry.terminalRejectCount,
    firstSeenIndex: entry.firstSeenIndex,
    lastSeenIndex: entry.lastSeenIndex,
    latestReceiptHash: entry.latestReceiptHash,
    score: entryScore(entry),
    retentionPriority: retentionPriority(entry, currentIndex, stalenessPenalty),
    entryHash: "",
  };
  return { ...snapshot, entryHash: await macroMemoryEntryHash(snapshot) };
}

function entryScore(entry                            )         {
  return 4 * entry.acceptedCount - 3 * entry.prefixRejectCount - 2 * entry.terminalRejectCount;
}

function retentionPriority(entry                            , currentIndex        , stalenessPenalty        )         {
  const evidence = 4 * entry.acceptedCount + 3 * entry.prefixRejectCount + 2 * entry.terminalRejectCount;
  const age = Math.max(0, currentIndex - entry.lastSeenIndex);
  return Math.max(0, evidence - stalenessPenalty * age);
}

function entryKey(context        , token        )         {
  return `${context}\n${token}`;
}

function receiptPayload(receipt         )                          {
  const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
    ? receipt.replayBundle                           
    : {};
  const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
    ? bundle.candidatePayload                           
    : {};
  return payload;
}

function macroStepsFromPayload      (payload                         )         {
  return Array.isArray(payload.macro) ? payload.macro           : [];
}

function isRecord(value         )                                   {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
