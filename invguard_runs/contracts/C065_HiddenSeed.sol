pragma solidity ^0.4.24;

contract HiddenSeed {
    uint256 private seed;
    uint256 public pot;

    constructor(uint256 _seed) public payable {
        seed = _seed;
        pot = msg.value;
    }

    function play(uint256 guess) public payable {
        require(msg.value == 0.1 ether);
        pot += msg.value;
        if (guess == uint256(keccak256(abi.encodePacked(seed, pot))) % 100) {
            uint256 prize = pot;
            pot = 0;
            msg.sender.transfer(prize);
        }
    }

    function version() public pure returns (uint256) {
        return 2;
    }
}
