from pooler.settings.config import settings

failed_query_epochs_redis_q = (
    'failedQueryEpochs:' + settings.namespace +
    ':{}:{}'
)

discarded_query_epochs_redis_q = (
    'discardedQueryEpochs:' + settings.namespace +
    ':{}:{}'
)

failed_commit_epochs_redis_q = (
    'failedCommitEpochs:' + settings.namespace +
    ':{}:{}'
)

cb_broadcast_processing_logs_zset = (
    'broadcastID:' + settings.namespace + ':{}:processLogs'
)

cached_block_details_at_height = (
    'uniswap:blockDetail:' + settings.namespace + ':blockDetailZset'
)
project_hits_payload_data_key = 'hitsPayloadData'
powerloom_broadcast_id_zset = (
    'powerloom:broadcastID:' + settings.namespace + ':broadcastProcessingStatus'
)
epoch_detector_last_processed_epoch = 'SystemEpochDetector:lastProcessedEpoch'

event_detector_last_processed_block = 'SystemEventDetector:lastProcessedBlock'

projects_dag_verifier_status = (
    'projects:' + settings.namespace + ':dagVerificationStatus'
)

uniswap_eth_usd_price_zset = (
    'uniswap:ethBlockHeightPrice:' + settings.namespace + ':ethPriceZset'
)

rpc_json_rpc_calls = (
    'rpc:jsonRpc:' + settings.namespace + ':calls'
)

rpc_get_event_logs_calls = (
    'rpc:eventLogsCount:' + settings.namespace + ':calls'
)

rpc_web3_calls = (
    'rpc:web3:' + settings.namespace + ':calls'
)

rpc_blocknumber_calls = (
    'rpc:blocknumber:' + settings.namespace + ':calls'
)


# project finalzed data zset
def project_finalized_data_zset(project_id):
    return f'projectID:{project_id}:finalizedData'

# project first epoch hashmap


def project_first_epoch_hmap():
    return 'projectFirstEpoch'


def cid_data(cid):
    return f'cidData:{cid}'


def source_chain_id_key():
    return 'sourceChainId'


def source_chain_block_time_key():
    return 'sourceChainBlockTime'


def source_chain_epoch_size_key():
    return 'sourceChainEpochSize'
