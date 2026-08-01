/**
 * Source Code first verified at https://etherscan.io on Tuesday, May 7, 2019
 (UTC) */

pragma solidity >= 0.5.0 < 0.6.0;


/**
 * @title PHO token - for Game coin sale
 * @author Willy Lee
 */


/**
 * @title ERC20 Standard Interface
 */
interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address who) external view returns (uint256);
    function transfer(address to, uint256 value) external returns (bool);
    event Transfer(address indexed from, address indexed to, uint256 value);
}


/**
 * @title Token implementation
 */
contract PHO is IERC20 {
  mapping(address => uint) balances;

  function transfer(address _to, uint _value) public returns (bool) {
    require(balances[msg.sender] >= _value);
    balances[msg.sender] -= _value;
    balances[_to] += _value;
    return true;
  }
  
  string public name = "PHO";
  string public symbol = "PHO";
  uint8 public decimals = 18;
    
  uint256 saleAmount;
  uint256 evtAmount;
  uint256 teamAmount;
  uint256 _totalSupply;

  constructor() public {
    balances[msg.sender] = toWei(2000000000); // 2,000,000,000
    _totalSupply = toWei(2000000000); // 2,000,000,000
    saleAmount = toWei(1000000000); // 1,000,000,000
    evtAmount = toWei(200000000); // 200,000,000
    teamAmount = toWei(800000000); // 800,000,000

    require(_totalSupply == saleAmount + evtAmount + teamAmount);
    emit Transfer(address(0), msg.sender, balances[msg.sender]);
    
    transfer(0x071F73f4D0befd4406901AACE6D5FFD6D297c561, saleAmount);
    transfer(0x76535ca5BF1d33434A302e5A464Df433BB1F80F6, evtAmount);
    transfer(0xD7EC5D8697e4c83Dc33D781d19dc2910fB165D5C, teamAmount);
    require(balances[msg.sender] == 0);
  }
    
  function totalSupply() public view returns (uint) {
    return _totalSupply;
  }

  function balanceOf(address who) public view returns (uint256) {
    return balances[who];
  }

  function burnCoins(uint256 value) public {
    require(balances[msg.sender] >= value);
    require(_totalSupply >= value);
    
    balances[msg.sender] -= value;
    _totalSupply -= value;

    emit Transfer(msg.sender, address(0), value);
  }

  function toWei(uint256 value) private view returns (uint256) {
    return value * (10 ** uint256(decimals));
  }
}