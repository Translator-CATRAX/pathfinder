import requests


def get_normalized_nodes(curies):
    url = 'https://nodenormalization-sri.renci.org/1.5/get_normalized_nodes'
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    payload = {
        "curies": curies,
        "conflate": True,
        "description": False,
        "drug_chemical_conflate": True
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Request failed: {e}")
        return None


def process_curies_in_batches(all_curies, batch_size=50):
    master_results = {}
    total_batches = (len(all_curies) + batch_size - 1) // batch_size

    for i in range(0, len(all_curies), batch_size):
        batch = all_curies[i:i + batch_size]
        batch_number = (i // batch_size) + 1

        print(f"Processing batch {batch_number} of {total_batches} ({len(batch)} CURIEs)...")
        batch_results = get_normalized_nodes(batch)

        if batch_results:
            for key, value in batch_results.items():
                if value is not None:
                    master_results[key] = value['id']['identifier']
        else:
            print(f"  -> Warning: Failed to get results for batch {batch_number}")

    return master_results


def normalized_legacy_dataset(input_data):
    all_nodes = set()
    for key, value in input_data:
        all_nodes.add(key)
        all_nodes.update(value)

    normalized_node = process_curies_in_batches(list(all_nodes), batch_size=100)

    result = []
    for key, value in input_data:
        if key in normalized_node:
            new_v = set()
            for v in value:
                if v in normalized_node:
                    new_v.add(normalized_node[v])
            result.append((normalized_node[key], new_v))
    return result


if __name__ == "__main__":
    my_large_list_of_nodes = [f"MESH:D0148{str(i).zfill(2)}" for i in range(125)]

    print(f"Total nodes to process: {len(my_large_list_of_nodes)}\n")

    final_results = process_curies_in_batches(my_large_list_of_nodes, batch_size=50)

    print("\nProcessing complete!")
    print(f"Successfully retrieved normalizations for {len(final_results)} nodes.")
