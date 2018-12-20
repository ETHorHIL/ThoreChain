# https://hackernoon.com/learn-blockchains-by-building-one-117428612f46
#             Step 2: Our Blockchain as an AP


import hashlib
import json
import request

from textwrap import dedent
from time import time
from uuid import uuid4
from urllib.parse import urlparse


from flask import Flask, jsonify, request

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        # Create genesis block
        self.new_block(previous_hash=1, proof=100)

    def  register_node(self, address):
        """
        Add a new node to the list of nodes

        :param address: <str> Address of node e.g. 'http://192.168.0.5:5000'
        :return: None

        """

        parsed_url =urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        """
        Determine if a given blockchain is valid

        :param chain: A blockchain
        :return: True if valid, false if not
        """

        last_block = chain[0]
        current_index=1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-------------\n")

            #check that the hash of the block is correct
            last_block_hash = self.hash(last_block)

            if block['previous_hash'] !=  last_block_hash:
                return False

            #check that the pow is correct
            if not self.valid_proof(last_block['proof'],block['proof']):
                return False

            last_block = block
            current_index +=1

        return True

    def resolve_conflicts(self):
        """
        This is our consensus algorithm, it resolves conflicts
        by replacing our chain with the longest chain

        :return: <bool> True if our chain was replaced, false if not
        """

        neighbours = self.nodes
        new_chain = None

        #Were only looking for chains longer than ours
        max_length = len(self.chain)

        #Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = request.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                #check if the length is longer and if the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        #Relace our chain if we discovered a longer valid chain
        if new_chain:
            self.chain =new_chain
            return True

        return False



    def new_block(self, proof, previous_hash):
        """
        creates a new block and adds it to the blockchain
        :param: proof <int> proof given by PoW
        :param previous_hash: previous_hash (Optional)<str> Hash of previous
        block
        :return: <dict> New Block
        """

        block = {
            'index': len(self.chain)+1,
            'timestamp': time(),
            'proof': proof,
            'previous_hash': previous_hash or hash(self.chain[-1]),
            'transactions': self.current_transactions,
        }

        # Reset the current list of current_transactions
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Creates a new transaction to go into the next mined block

        :param sender: <str> Address of the sender
        :param recipient: <str> Address of the recipient
        :param amount:  <int> Amount of the transaction
        :return: <int> The index of the block that will hold this transaction
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index']+1

    @staticmethod
    def hash(block):
        """
        creates a shah 256 hash of the block
        :param block: <dict> Block
        return <str>
        """

        # We must make sure the dict is ordered or we have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """
        Simple proof of work algorithm
        find a number p so that hash(pp') contains 4 leading zeroes where p' is
        the current proof and p the last proof

        :param last_proof: <int> last block PoW
        :return: <int>
        """

        proof = 0

        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
            """
            Validates the Proof: Does hash(last_proof, proof) contain 4 leading zeroes?

            checks if proof is valid
            :param last_proof: <int> Previous proof
            :param proof: <int> current proof
            :return: <bool> true if correct
            """

            guess = f'{last_proof}{proof}'.encode()
            guess_hash = hashlib.sha256(guess).hexdigest()
            return guess_hash[:4] == "0000"

#instantiate the node
app = Flask(__name__)

#Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-','')

#instantiate the blockchain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():

    #We run the proof of work algorithm to get the next proof...
    last_block = blockchain.last_block
    last_proof = last_block['proof']

    proof = blockchain.proof_of_work(last_proof)

    #we must receive a reward for finding the proof
    #the sender is '0' to signify that this node has found the proof

    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1
    )

    #forge the new block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof,previous_hash)

    response = {
        'message': "New Block forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():

    values = request.get_json()

    #check that the required fields are in the posted data
    required = ['sender','recipient','amount']

    if not all(k in values for k in required):
        return 'missing value', 400

    #create a new transaction
    index = blockchain.new_transaction(values['sender'],values['recipient'],values['amount'])

    repsonse = {'message': f'Transaction will be added to block {index}'}

    return jsonify(repsonse), 201


@app.route('/chain',methods=['GET'])
def full_chain():
    response = {
        'chain':blockchain.chain,
        'length':len(blockchain.chain),
    }

    return jsonify(response), 200


@app.route('/nodes/register',methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please submit a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response ={
        'message':'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }

    return jsonify(response), 201

@app.route('/nodes/resolve',methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': "Our chain is authoritative",
            'new_chain': blockchain.chain
        }

    else:
        response = {
            'message': "Our chain is authoritative",
            'new_chain': blockchain.chain
        }

    return  jsonify(response), 200




if __name__ ==  '__main__':

    #from argparse import ArgumentParser
    #parser = ArgumentParser()
    #parser.add_argument('-p','--port',default=5000,type=int,help= 'port to listen on')
    #args= parser.parse_args()
    #port =args.port

    app.run(host='0.0.0.0',port=5000)