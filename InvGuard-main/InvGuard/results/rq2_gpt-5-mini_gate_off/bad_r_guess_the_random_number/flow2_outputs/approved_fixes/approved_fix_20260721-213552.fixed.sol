pragma solidity ^0.4.21;

contract GuessTheRandomNumberChallenge {
    uint8 answer;

    // commit-reveal storage
    mapping(address => bytes32) public commitments;
    mapping(address => uint256) public commitBlock;

    // reentrancy mutex
    bool private _locked;

    function GuessTheRandomNumberChallenge() public payable {
        require(msg.value == 1 ether);
        // <yes> <report> BAD_RANDOMNESS
        answer = uint8(keccak256(block.blockhash(block.number - 1), now));
    }

    function isComplete() public view returns (bool) {
        return address(this).balance == 0;
    }

    // commit must be submitted in a prior block:
    // user computes keccak256(uint8 n, address submitter) off-chain and calls commit with that value,
    // then in a later block calls guess(n) with 1 ether to reveal and attempt the payout.
    function commit(bytes32 c) public {
        require(commitments[msg.sender] == 0); // prevent overwrite without reveal
        commitments[msg.sender] = c;
        commitBlock[msg.sender] = block.number;
    }

    function guess(uint8 n) public payable {
        require(!_locked);
        _locked = true;

        require(msg.value == 1 ether);

        // require a prior commit and that it was made in a previous block (prevents same-block prediction)
        require(commitments[msg.sender] != 0);
        require(commitBlock[msg.sender] != 0);
        require(block.number > commitBlock[msg.sender]);

        // verify the reveal matches the prior commit; commit must have been keccak256(n, msg.sender)
        require(commitments[msg.sender] == keccak256(n, msg.sender));

        // clear state before any external call (CEI)
        commitments[msg.sender] = 0;
        commitBlock[msg.sender] = 0;

        if (n == answer) {
            msg.sender.transfer(2 ether);
        }

        _locked = false;
    }
}
